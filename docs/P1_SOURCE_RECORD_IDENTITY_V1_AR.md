# P1 — Source Record Identity and Vintage Contract V1

**Status:** isolated implementation candidate; unit-tested locally, awaiting repository CI.
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

## Local verification

\`\`\`bash
python -m unittest discover -s tests/observation_foundation -v
python -m py_compile observation_foundation/record_identity_v1.py
python -m json.tool observation_foundation/contracts/source_record_observation_v1.schema.json
\`\`\`

The local unit suite currently covers identity stability across re-imports, revisions, natural-key ordering, missing stable keys, multiplicity, numeric/time normalization, and point-in-time selection. Passing these tests verifies the helper's specified behavior, not yet its integration with every CHAOS source adapter.
