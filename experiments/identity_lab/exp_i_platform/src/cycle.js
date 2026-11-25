/**
 * First real run of the fixture cycle against the platform module itself:
 * seed a broken run -> audit -> export -> purge -> prove the real event survived.
 */
const path = require('path');

class MemoryStorage {
  constructor() { this.map = new Map(); }
  get length() { return this.map.size; }
  clear() { this.map.clear(); }
  getItem(k) { return this.map.has(k) ? this.map.get(k) : null; }
  key(i) { return [...this.map.keys()][i] ?? null; }
  removeItem(k) { this.map.delete(k); }
  setItem(k, v) { this.map.set(k, String(v)); }
}
globalThis.localStorage = new MemoryStorage();

const fx = require('./fixtureSeeds.js');

const real = {
  eventId: 'real-42', schemaVersion: 1, entityType: 'request', entityId: 'req-real-42',
  relatedRequestId: null, eventType: 'request_created', occurredAt: '2025-10-01T06:00:00.000Z',
  recordedAt: '2025-10-01T06:00:00.000Z', actorId: 'pharmacy-aden-1', actorType: 'pharmacy',
  source: 'web_client', idempotencyKey: 'real-42', metadata: {},
};
localStorage.setItem(fx.EVENTS_STORAGE_KEY, JSON.stringify([real]));

const run = fx.seedMatchLifecycle({ runId: 'fx-2025-10-01-audit', withViolation: true, startedAt: new Date('2025-10-01T08:00:00Z') });
const streamAfterSeed = JSON.parse(localStorage.getItem(fx.EVENTS_STORAGE_KEY) || '[]');
const visible = fx.publicEvents(streamAfterSeed);
const audit = fx.auditSingleOccurrence(streamAfterSeed);
const summary = fx.fixtureRunsSummary();
const purged = fx.purgeFixtureRun(run.runId);
const streamAfterPurge = JSON.parse(localStorage.getItem(fx.EVENTS_STORAGE_KEY) || '[]');

const out = {
  generated_at: new Date().toISOString(),
  run_id: run.runId,
  seeded_events: run.events.length,
  violations: run.violations,
  stream_total_after_seed: streamAfterSeed.length,
  visible_to_users_after_seed: visible.length,
  admin_runs: summary,
  purge: purged,
  stream_total_after_purge: streamAfterPurge.length,
  real_event_survived: streamAfterPurge.some((e) => e.eventId === real.eventId),
  seeded_events_detail: run.events.map((e) => ({ eventId: e.eventId, eventType: e.eventType,
    entityType: e.entityType, entityId: e.entityId, relatedRequestId: e.relatedRequestId,
    occurredAt: e.occurredAt, fixtureRun: e.metadata.fixtureRun })),
};
console.log(JSON.stringify(out, null, 2));
