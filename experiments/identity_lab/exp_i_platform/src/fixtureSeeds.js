"use strict";
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.fixtureRunsSummary = exports.purgeFixtureRun = exports.auditSingleOccurrence = exports.seedMatchLifecycle = exports.loadFixtureEvents = exports.publicEvents = exports.isFixtureRun = exports.isFixtureEvent = exports.makeRunId = exports.FIXTURE_ACTOR_ID = exports.FIXTURE_RUN_PREFIX = exports.IDEMPOTENCY_STORAGE_KEY = exports.EVENTS_STORAGE_KEY = void 0;
exports.EVENTS_STORAGE_KEY = 'pharmayemen_events_stream_v1';
exports.IDEMPOTENCY_STORAGE_KEY = 'pharmayemen_idempotency_keys_v1';
exports.FIXTURE_RUN_PREFIX = 'fx-';
exports.FIXTURE_ACTOR_ID = 'fixture_seed';
const readJson = (key) => {
    try {
        const raw = typeof localStorage === 'undefined' ? '[]' : localStorage.getItem(key);
        return raw ? JSON.parse(raw) : [];
    }
    catch {
        return [];
    }
};
const writeJson = (key, value) => {
    if (typeof localStorage === 'undefined')
        return;
    localStorage.setItem(key, JSON.stringify(value));
};
const makeRunId = (at = new Date()) => `${exports.FIXTURE_RUN_PREFIX}${at.toISOString().slice(0, 10).replace(/-/g, '')}-${Math.random()
    .toString(36)
    .slice(2, 6)}`;
exports.makeRunId = makeRunId;
const isFixtureEvent = (event) => Boolean(event && event.metadata && event.metadata.fixture === true);
exports.isFixtureEvent = isFixtureEvent;
const isFixtureRun = (event, runId) => Boolean(event && event.metadata && event.metadata.fixtureRun === runId);
exports.isFixtureRun = isFixtureRun;
/** Everything user-facing must go through this. Fixtures never reach a screen. */
const publicEvents = (events) => events.filter((event) => !(0, exports.isFixtureEvent)(event));
exports.publicEvents = publicEvents;
/** Fixtures only. This is what analytics and the detector read when they ask for the seed corpus. */
const loadFixtureEvents = (runId) => {
    const all = readJson(exports.EVENTS_STORAGE_KEY);
    return all.filter((event) => (0, exports.isFixtureEvent)(event) && (!runId || (0, exports.isFixtureRun)(event, runId)));
};
exports.loadFixtureEvents = loadFixtureEvents;
const buildEvent = (runId, seq, base, startedAt, offsetMinutes) => {
    const at = new Date(startedAt.getTime() + offsetMinutes * 60000).toISOString();
    return {
        ...base,
        eventId: `${runId}-evt-${seq}`,
        schemaVersion: 1,
        occurredAt: at,
        recordedAt: at,
        actorId: exports.FIXTURE_ACTOR_ID,
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
const seedMatchLifecycle = (options = {}) => {
    const runId = options.runId || (0, exports.makeRunId)(options.startedAt || new Date());
    const startedAt = options.startedAt || new Date();
    const requestId = `${runId}-req-1`;
    const offerId = `${runId}-off-1`;
    const matchId = `${runId}-mat-1`;
    const events = [
        buildEvent(runId, 1, { entityType: 'request', entityId: requestId, relatedRequestId: null, eventType: 'request_created' }, startedAt, 0),
        buildEvent(runId, 2, { entityType: 'offer', entityId: offerId, relatedRequestId: requestId, eventType: 'offer_created' }, startedAt, 45),
        buildEvent(runId, 3, { entityType: 'match', entityId: matchId, relatedRequestId: requestId, eventType: 'match_proposed' }, startedAt, 90),
        buildEvent(runId, 4, { entityType: 'match', entityId: matchId, relatedRequestId: requestId, eventType: 'match_confirmed' }, startedAt, 120),
    ];
    if (options.withViolation) {
        events.push(buildEvent(runId, 5, { entityType: 'match', entityId: `${runId}-mat-2`, relatedRequestId: requestId, eventType: 'match_confirmed' }, startedAt, 121));
    }
    const stream = readJson(exports.EVENTS_STORAGE_KEY);
    const known = new Set(stream.map((event) => event.idempotencyKey));
    const fresh = events.filter((event) => !known.has(event.idempotencyKey));
    writeJson(exports.EVENTS_STORAGE_KEY, [...stream, ...fresh]);
    const keys = readJson(exports.IDEMPOTENCY_STORAGE_KEY);
    const knownKeys = new Set(keys);
    writeJson(exports.IDEMPOTENCY_STORAGE_KEY, [...keys, ...fresh.map((event) => event.idempotencyKey).filter((key) => !knownKeys.has(key))]);
    return { runId, events: fresh, violations: (0, exports.auditSingleOccurrence)(fresh) };
};
exports.seedMatchLifecycle = seedMatchLifecycle;
/**
 * The single-occurrence identity, applied to the platform's own events:
 * one request may be confirmed once. This is the same statement as one H1 per session.
 */
const auditSingleOccurrence = (events) => {
    const byRequest = new Map();
    for (const event of events) {
        if (event.eventType !== 'match_confirmed' || !event.relatedRequestId)
            continue;
        const list = byRequest.get(event.relatedRequestId) || [];
        list.push(event.eventId);
        byRequest.set(event.relatedRequestId, list);
    }
    return [...byRequest.entries()]
        .filter(([, ids]) => ids.length > 1)
        .map(([requestId, ids]) => ({ requestId, confirmations: ids.length, eventIds: ids }));
};
exports.auditSingleOccurrence = auditSingleOccurrence;
/** Removes one run completely: its events and its idempotency keys. Returns what it removed. */
const purgeFixtureRun = (runId) => {
    const stream = readJson(exports.EVENTS_STORAGE_KEY);
    const kept = stream.filter((event) => !(0, exports.isFixtureRun)(event, runId));
    writeJson(exports.EVENTS_STORAGE_KEY, kept);
    const keys = readJson(exports.IDEMPOTENCY_STORAGE_KEY);
    const prefix = `fixture:${runId}:`;
    const keptKeys = keys.filter((key) => typeof key === 'string' ? !key.startsWith(prefix) : true);
    writeJson(exports.IDEMPOTENCY_STORAGE_KEY, keptKeys);
    return { removedEvents: stream.length - kept.length, removedKeys: keys.length - keptKeys.length };
};
exports.purgeFixtureRun = purgeFixtureRun;
/** Admin view: one row per fixture run, with what it contains. */
const fixtureRunsSummary = () => {
    const fixtures = (0, exports.loadFixtureEvents)();
    const byRun = new Map();
    for (const event of fixtures) {
        const runId = String(event.metadata.fixtureRun);
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
exports.fixtureRunsSummary = fixtureRunsSummary;
