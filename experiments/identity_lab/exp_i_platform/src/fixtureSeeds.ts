/**
 * Fixture provenance layer.
 *
 * A fixture is a synthetic event run that lives inside the real event stream, is invisible to
 * every user-facing view, and can be removed exactly and completely. It exists so the analytics
 * and the CHAOS detectors can be exercised on the platform's own event shapes instead of on a
 * foreign CSV.
 *
 * Three rules, and they are not negotiable:
 *   1. every fixture event carries `metadata.fixture === true` and `metadata.fixtureRun`;
 *   2. `publicEvents()` is the only reader user-facing code should use;
 *   3. `purgeFixtureRun()` removes the run and its idempotency keys, nothing else.
 */

export const EVENTS_STORAGE_KEY = 'pharmayemen_events_stream_v1';
export const IDEMPOTENCY_STORAGE_KEY = 'pharmayemen_idempotency_keys_v1';
export const FIXTURE_RUN_PREFIX = 'fx-';
export const FIXTURE_ACTOR_ID = 'fixture_seed';

export interface FixtureMetadata {
  fixture: true;
  fixtureRun: string;
  fixtureNote?: string;
}

export interface FixtureEvent {
  eventId: string;
  schemaVersion: number;
  entityType: 'request' | 'offer' | 'match' | 'ticket' | 'broadcast';
  entityId: string;
  relatedRequestId: string | null;
  eventType: string;
  occurredAt: string;
  recordedAt: string;
  actorId: string;
  actorType: string;
  source: string;
  idempotencyKey: string;
  metadata: Record<string, unknown>;
}

const readJson = <T,>(key: string): T[] => {
  try {
    const raw = typeof localStorage === 'undefined' ? '[]' : localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T[]) : [];
  } catch {
    return [];
  }
};

const writeJson = (key: string, value: unknown[]): void => {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(key, JSON.stringify(value));
};

export const makeRunId = (at: Date = new Date()): string =>
  `${FIXTURE_RUN_PREFIX}${at.toISOString().slice(0, 10).replace(/-/g, '')}-${Math.random()
    .toString(36)
    .slice(2, 6)}`;

export const isFixtureEvent = (event: { metadata?: Record<string, unknown> | null }): boolean =>
  Boolean(event && event.metadata && (event.metadata as Record<string, unknown>).fixture === true);

export const isFixtureRun = (event: { metadata?: Record<string, unknown> | null }, runId: string): boolean =>
  Boolean(event && event.metadata && (event.metadata as Record<string, unknown>).fixtureRun === runId);

/** Everything user-facing must go through this. Fixtures never reach a screen. */
export const publicEvents = <T extends { metadata?: Record<string, unknown> | null }>(events: T[]): T[] =>
  events.filter((event) => !isFixtureEvent(event));

/** Fixtures only. This is what analytics and the detector read when they ask for the seed corpus. */
export const loadFixtureEvents = (runId?: string): FixtureEvent[] => {
  const all = readJson<FixtureEvent>(EVENTS_STORAGE_KEY);
  return all.filter((event) => isFixtureEvent(event) && (!runId || isFixtureRun(event, runId)));
};

export interface SeedOptions {
  runId?: string;
  /** adds the deliberate single-occurrence break: two confirmations for one request */
  withViolation?: boolean;
  /** clock for deterministic tests */
  startedAt?: Date;
}

export interface SeedResult {
  runId: string;
  events: FixtureEvent[];
  violations: ReturnType<typeof auditSingleOccurrence>;
}

const buildEvent = (
  runId: string,
  seq: number,
  base: Omit<FixtureEvent, 'eventId' | 'schemaVersion' | 'occurredAt' | 'recordedAt' | 'actorId' | 'actorType' | 'source' | 'idempotencyKey' | 'metadata'>,
  startedAt: Date,
  offsetMinutes: number,
): FixtureEvent => {
  const at = new Date(startedAt.getTime() + offsetMinutes * 60_000).toISOString();
  return {
    ...base,
    eventId: `${runId}-evt-${seq}`,
    schemaVersion: 1,
    occurredAt: at,
    recordedAt: at,
    actorId: FIXTURE_ACTOR_ID,
    actorType: 'system_cron',
    source: 'admin_action',
    idempotencyKey: `fixture:${runId}:${seq}`,
    metadata: { fixture: true, fixtureRun: runId, fixtureNote: 'seeded lifecycle' },
  };
};

/**
 * Seeds one request -> offer -> match lifecycle.
 * With `withViolation`, it adds a second confirmation for the same request: the exact fault
 * the single-occurrence identity forbids, and the analogue of a second H1.
 */
export const seedMatchLifecycle = (options: SeedOptions = {}): SeedResult => {
  const runId = options.runId || makeRunId(options.startedAt || new Date());
  const startedAt = options.startedAt || new Date();
  const requestId = `${runId}-req-1`;
  const offerId = `${runId}-off-1`;
  const matchId = `${runId}-mat-1`;

  const events: FixtureEvent[] = [
    buildEvent(runId, 1, { entityType: 'request', entityId: requestId, relatedRequestId: null, eventType: 'request_created' }, startedAt, 0),
    buildEvent(runId, 2, { entityType: 'offer', entityId: offerId, relatedRequestId: requestId, eventType: 'offer_created' }, startedAt, 45),
    buildEvent(runId, 3, { entityType: 'match', entityId: matchId, relatedRequestId: requestId, eventType: 'match_proposed' }, startedAt, 90),
    buildEvent(runId, 4, { entityType: 'match', entityId: matchId, relatedRequestId: requestId, eventType: 'match_confirmed' }, startedAt, 120),
  ];

  if (options.withViolation) {
    events.push(
      buildEvent(runId, 5, { entityType: 'match', entityId: `${runId}-mat-2`, relatedRequestId: requestId, eventType: 'match_confirmed' }, startedAt, 121),
    );
  }

  const stream = readJson<FixtureEvent>(EVENTS_STORAGE_KEY);
  const known = new Set(stream.map((event) => event.idempotencyKey));
  const fresh = events.filter((event) => !known.has(event.idempotencyKey));
  writeJson(EVENTS_STORAGE_KEY, [...stream, ...fresh]);

  const keys = readJson<string>(IDEMPOTENCY_STORAGE_KEY);
  const knownKeys = new Set(keys);
  writeJson(IDEMPOTENCY_STORAGE_KEY, [...keys, ...fresh.map((event) => event.idempotencyKey).filter((key) => !knownKeys.has(key))]);

  return { runId, events: fresh, violations: auditSingleOccurrence(fresh) };
};

export interface OccurrenceViolation {
  requestId: string;
  confirmations: number;
  eventIds: string[];
}

/**
 * The single-occurrence identity, applied to the platform's own events:
 * one request may be confirmed once. This is the same statement as one H1 per session.
 */
export const auditSingleOccurrence = (events: Array<{ eventType: string; relatedRequestId?: string | null; eventId: string }>): OccurrenceViolation[] => {
  const byRequest = new Map<string, string[]>();
  for (const event of events) {
    if (event.eventType !== 'match_confirmed' || !event.relatedRequestId) continue;
    const list = byRequest.get(event.relatedRequestId) || [];
    list.push(event.eventId);
    byRequest.set(event.relatedRequestId, list);
  }
  return [...byRequest.entries()]
    .filter(([, ids]) => ids.length > 1)
    .map(([requestId, ids]) => ({ requestId, confirmations: ids.length, eventIds: ids }));
};

/** Removes one run completely: its events and its idempotency keys. Returns what it removed. */
export const purgeFixtureRun = (runId: string): { removedEvents: number; removedKeys: number } => {
  const stream = readJson<FixtureEvent>(EVENTS_STORAGE_KEY);
  const kept = stream.filter((event) => !isFixtureRun(event, runId));
  writeJson(EVENTS_STORAGE_KEY, kept);

  const keys = readJson<string>(IDEMPOTENCY_STORAGE_KEY);
  const prefix = `fixture:${runId}:`;
  const keptKeys = keys.filter((key) => typeof key === 'string' ? !key.startsWith(prefix) : true);
  writeJson(IDEMPOTENCY_STORAGE_KEY, keptKeys);

  return { removedEvents: stream.length - kept.length, removedKeys: keys.length - keptKeys.length };
};

/** Admin view: one row per fixture run, with what it contains. */
export const fixtureRunsSummary = (): Array<{ runId: string; events: number; firstAt: string; lastAt: string }> => {
  const fixtures = loadFixtureEvents();
  const byRun = new Map<string, FixtureEvent[]>();
  for (const event of fixtures) {
    const runId = String((event.metadata as Record<string, unknown>).fixtureRun);
    byRun.set(runId, [...(byRun.get(runId) || []), event]);
  }
  return [...byRun.entries()]
    .map(([runId, list]) => ({
      runId,
      events: list.length,
      firstAt: list.map((event) => event.occurredAt).sort()[0],
      lastAt: list.map((event) => event.occurredAt).sort().slice(-1)[0],
    }))
    .sort((a, b) => a.runId.localeCompare(b.runId));
};
