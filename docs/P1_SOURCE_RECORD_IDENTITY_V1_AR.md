# P1 — Source Record Identity and Vintage Contract V1

**Status:** source identity integrated into the WDI Trade DomainState builder; CI passed for the integration path. Point-in-time eligibility remains unknown because the committed WDI extract does not expose historical availability/vintage metadata.
**Branch:** `discovery/d1-domainstate-integrity-v1`

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

## Revision status and native time support

- Each source-record version carries `revision_status` as a provider-native string or explicit `null` when the provider exposes no revision state. It participates in the canonical version digest; it does not change the stable logical record ID.
- Each source/dataset/series declares `time_support` separately from its individual observations: `observation_period_start`, `observation_period_end`, and `native_frequency`.
- The envelope has its own JSON Schema: `observation_foundation/contracts/observation_time_support_v1.schema.json`. It is not embedded in `source_record_observation_v1.schema.json` because period coverage belongs to a series/collection, not an individual observation.
- `normalize_time_support(...)` is the runtime semantic validator; it preserves native year/month/day labels or timezone-aware instants, defaults `boundary_semantics` to `SOURCE_DECLARED`, and rejects missing, reversed, blank, or unrecognized values.
- `build_epoch_snapshot(..., time_support=...)` persists this envelope in the content-addressed manifest. An omitted envelope is retained as `NOT_DECLARED`; a reversed interval is rejected. The envelope does not participate in individual `logical_record_id` or `canonical_record_id` hashes.
- Same-`available_at` conflicting versions remain `AMBIGUOUS_SAME_AVAILABLE_AT`; no lexical source-revision or ingest-order tie-break is introduced.

## Verification commands

\`\`\`bash
python -m unittest discover -s tests/observation_foundation -v
python -m py_compile observation_foundation/record_identity_v1.py
python -m json.tool observation_foundation/contracts/source_record_observation_v1.schema.json
\`\`\`

The committed unit suite covers identity stability across re-imports, revisions, natural-key ordering, missing stable keys, multiplicity, numeric/time normalization, subsecond vintage ordering, point-in-time selection, epoch digest stability, stale-content rejection, and exclusion accounting. A green CI run is required before calling these checks passed; adapter integration remains separate.


## Additional P1 rule — periodic measurement slot identity

When series_semantics is periodic_measurement and neither a stable source ID nor an explicit natural key is provided, the contract derives the logical slot from entity_id + metric_id + event_time, scoped by source_namespace + dataset_id. This is valid only for the declared one-value-per-series-period semantics. It is not applied to event_stream or period_count, where occurrence multiplicity must remain intact.

## WDI Trade source-identity integration — 2026-11-21

The identity contract is now applied **to the raw WDI observation row before the DomainState is emitted**, not reconstructed from the derived DomainState.

Implementation:
- Adapter: `scripts/adapters/build_wdi_trade_domain_states.py`.
- Source namespace: `world_bank`.
- Stable dataset identifier: `wdi_country_annual_indicators`.
- Semantics: `periodic_measurement`.
- Logical slot: country code + indicator code + source year, scoped by source namespace and dataset.
- Canonical version identity: the logical slot plus the numeric value, source unit, event time and declared version fields.
- Original source value lexeme remains untouched in `source_observations.value_raw`.
- The JSON numeric value is accepted only when `Decimal(str(float(value)))` exactly round-trips to the parsed source decimal. A value that would lose decimal precision fails closed.
- The DomainState carries `source_record_identity` with logical ID, canonical ID, identity basis, and explicit point-in-time eligibility.

Verified output:
- 29,004 DomainStates, 259 entities, five indicators, annual 2000–2024.
- 29,004 unique logical slots and 29,004 unique canonical versions.
- Zero duplicate source slots.
- Source-declared coverage envelope: 2000–2024, annual.
- Workflow `44943154074` passed: 8 adapter tests, deterministic build, and the central DomainState registry audit command.
- Output SHA-256: `c4f836acc9f57c35f605447def2e0dc412d1363a917b534f0ffde30932729554`.

Important source limitation:
- All 29,004 observations have `available_at = null`; none exposes a usable historical release/vintage timestamp in the committed extract.
- The identity is valid for stable source-slot and content-version lineage, but these observations are **not point-in-time eligible** for an as-of historical information set. No retrieval date was substituted for an unavailable release date.
- The source extract exposes no revision ID/status, so those fields remain null. A later data vintage must be ingested as a new version only when its source availability/revision evidence is known.

The registry audit saw 94,231 records and zero invalid records, but its overall result remained `BLOCKED_INCOMPLETE_ASSET_SET`: six registered files are absent (four IMF IMTS shards, the WHO daily DomainState artifact, and the WGI institutional DomainState artifact). This is a multi-domain asset-coverage blocker, not a failure of the WDI adapter. The missing assets remain visible; none were fabricated or silently removed.
