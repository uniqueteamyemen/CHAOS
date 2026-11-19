# P1 — Source Record Identity and Vintage Contract V1

**Status:** isolated implementation candidate; deterministic tests are committed; repository CI result is not yet verified.
**Branch:** \`fix/p2-2-3-gem-snapshot\`

## Purpose

Add deterministic identity for source observations without changing the existing business-identity contract \`identity_v1\`, residual-event contract \`residual_event_v1\`, frozen detector, or historical experiment archive.

## Identity model

- \`logical_record_id\`: stable across revisions only when the provider supplies a stable \`source_record_id\`, or the adapter explicitly declares a defensible natural key in \`logical_key\`. It is scoped by \`source_namespace\` and \`dataset_id\`.
- \`canonical_record_id\`: SHA-256 of the canonical version payload. It changes when the value, status, unit, event time, availability time, source revision, entity, metric, or source identity changes.
- A revision chain is represented by all immutable canonical records sharing one logical ID, ordered by \`available_at\`. Previous versions are never overwritten.
- If no stable logical key exists, \`logical_record_id\` is null and the result is explicitly \`UNRESOLVED_NO_STABLE_KEY\`. No row number, retrieval timestamp, or arrival sequence is used to invent linkage.

## Canonicalization

- UTF-8 JSON; Unicode NFC; sorted object keys; compact separators.
- Finite decimal values are normalized so equivalent values such as \`5\` and \`5.0\` hash identically.
- Timezone-aware datetimes are normalized to UTC; native year/month/day labels remain native event-time labels.
- \`available_at\` must be a timezone-aware instant. Null means point-in-time eligibility is unknown.
- Retrieval and transport fields (\`retrieved_at\`, \`ingest_batch_id\`, \`row_number\`) are audit-only and excluded from both IDs.

## Multiplicity

The utility never deduplicates:
- \`event_stream\` and \`period_count\`: \`PRESERVE_EACH_OCCURRENCE\`.
- \`periodic_measurement\`: preserve until a source contract proves a duplicate transport delivery.

Identical content can legitimately produce the same canonical ID more than once. The records remain multiple occurrences. A digest identifies content, not a uniquely distinguishable physical copy when the source supplies no distinguishing key.

## Point-in-time selection

\`select_vintages_as_of(records, decision_time)\`:
1. Excludes records with unknown \`available_at\`.
2. Ignores vintages arriving after the decision time.
3. Selects the latest available vintage for each stable logical ID.
4. Returns an ambiguity instead of a lexical or arrival-order tie-break if different canonical versions share the latest \`available_at\`.
5. Retains unlinked records as standalone observations; it cannot infer their revision chains.
6. Compares availability timestamps as actual UTC instants, not lexical ISO strings; subsecond vintages remain correctly ordered.

## Epoch snapshot V1

`build_epoch_snapshot(records, decision_time)` creates a deterministic, content-addressed point-in-time manifest:

- Applies the as-of vintage selector and preserves every selected occurrence, including repeated canonical IDs for event/count multiplicity.
- Records source namespace/dataset lineage, decision time, selected canonical IDs, unlinked occurrence count, conflicting same-time vintages, and exclusions for unknown/future availability.
- Recomputes each source record identity before snapshotting; a record whose content no longer matches its canonical digest is rejected.
- Computes `epoch_id = epoch:v1:sha256:<digest>` from the canonical manifest. Input order and transport metadata do not affect the digest; selected multiplicity and decision time do.
- Returns the selected normalized records alongside the manifest so downstream computation can consume exactly the frozen point-in-time set.

This is a deterministic snapshot builder, not yet a storage service or integration with every source adapter. Adapter wiring and immutable artifact persistence remain subsequent P1 integration work.

## Verification commands

\`\`\`bash
python -m unittest discover -s tests/observation_foundation -v
python -m py_compile observation_foundation/record_identity_v1.py
python -m json.tool observation_foundation/contracts/source_record_observation_v1.schema.json
\`\`\`

The committed unit suite covers identity stability across re-imports, revisions, natural-key ordering, missing stable keys, multiplicity, numeric/time normalization, subsecond vintage ordering, point-in-time selection, epoch digest stability, stale-content rejection, and exclusion accounting. A green CI run is required before calling these checks passed; adapter integration remains separate.


## Additional P1 rule — periodic measurement slot identity

When series_semantics is periodic_measurement and neither a stable source ID nor an explicit natural key is provided, the contract derives the logical slot from entity_id + metric_id + event_time, scoped by source_namespace + dataset_id. This is valid only for the declared one-value-per-series-period semantics. It is not applied to event_stream or period_count, where occurrence multiplicity must remain intact.
