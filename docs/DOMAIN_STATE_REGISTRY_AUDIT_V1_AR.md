# CHAOS — DomainState Registry Integrity Audit V1

**Source of evidence:** GitHub Actions run [44952544505](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44952544505), on candidate SHA `4c9b0c2219d6f0b834a80947a24819d268eb4ccb`; the PR-head validation rerun is recorded in [44953200015](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44953200015).  
**Read-only audit artifact:** `DOMAIN_STATE_INTEGRITY_REPORT_V2.json`, artifact ID `14725898366`.  
**Integration status:** PR [#28](https://github.com/uniqueteamyemen/CHAOS/pull/28) merged into `main-phase2` at `e0c13b41ef1bbbdfe46f1dc266a007eb2dedd8d7`.  
**Important:** This report describes asset completeness at the audited SHA. It is not a scientific acceptance certificate.

## 1. Registry result

| Metric | Observed |
|---|---:|
| Registered asset paths | 21 |
| Existing/readable assets | 15 |
| Missing asset paths | 6 |
| Records read from existing assets | 94,231 |
| Schema-invalid records | 0 |
| Registry readiness | `BLOCKED_INCOMPLETE_ASSET_SET` |

The GitHub Actions job itself concluded `success` because the auditor and its unit tests executed successfully and found no malformed records. The validator intentionally returns a successful process status for `BLOCKED_INCOMPLETE_ASSET_SET`; that is an audit-execution result, **not** a readiness PASS. The report's readiness field is authoritative for asset completeness.

## 2. Exact missing references

The current Git tree at the candidate does not contain these six registered files:

| Missing path | Location | Interpretation |
|---|---|---|
| `campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_DOMAIN_STATES_ANNUAL_SOURCE_YEARS_V1.jsonl` | Active campaign area | WGI adapter summary reports 32,403 estimated DomainStates, but the expected materialized output is absent from the Git tree. No builder/input bundle is established by the artifacts read here. |
| `experiments/multi_domain_native_adapters_v1/WHO_COVID_DOMAIN_STATES_DAILY_V1.jsonl.gz` | Protected historical archive | Referenced by the registry but absent at this exact path. Do not reconstruct or add it under the current immutability mandate. |
| `experiments/multi_domain_native_adapters_v1/imf_imts_v1/domain_state_shards/IMF_IMTS_DOMAIN_STATES_BRA_ANNUAL_V1.jsonl` | Protected historical archive | Registered path absent. |
| `experiments/multi_domain_native_adapters_v1/imf_imts_v1/domain_state_shards/IMF_IMTS_DOMAIN_STATES_CAN_ANNUAL_V1.jsonl` | Protected historical archive | Registered path absent. |
| `experiments/multi_domain_native_adapters_v1/imf_imts_v1/domain_state_shards/IMF_IMTS_DOMAIN_STATES_MEX_ANNUAL_V1.jsonl` | Protected historical archive | Registered path absent. |
| `experiments/multi_domain_native_adapters_v1/imf_imts_v1/domain_state_shards/IMF_IMTS_DOMAIN_STATES_ZAF_ANNUAL_V1.jsonl` | Protected historical archive | Registered path absent. |

The five absent paths under `experiments/**` are read-only historical references for this work. Their absence is not permission to recreate, rename, move, or otherwise modify the archive. The WGI output is the only missing path outside the protected experiment tree; its presence must be established by a separately reproducible adapter run with a traceable source input before it can be counted as available.

## 3. Coarse-key collisions in archived IMF IMTS shards

The original audit field `duplicate_state_slots` was based on a key containing only:

`domain + entity_id + pattern_id + timestamp + native_frequency`

The archived IMF IMTS shard records use the same generic `pattern_id = IMF_IMTS_SOURCE_OBSERVATION_STATE_V1` for one country/year while carrying distinct source dimensions inside `source_observations`, including `counterpart_country`, `indicator`, `trade_flow`, and `valuation`. A representative CHN record has counterpart `ABW`, indicator `XG_FOB_USD`, and flow `XG`; other records at the same country/year may legitimately have different counterpart/indicator/flow combinations.

Therefore those earlier counts were **coarse-key collisions, not proven duplicate observations**. Across 11 existing archived IMF shards, the earlier report counted 59,553 collisions in that coarse key. The counts were:
- CHN 5,523; DEU 5,619; FRA 5,606; GBR 5,596; IND 5,511; ITA 5,592;
- JPN 5,497; KOR 5,544; SAU 4,059; TUR 5,470; USA 5,536.

No records were removed. The validator was corrected in the Discovery candidate to call this measurement `coarse_identity_collisions`, expose the operation as `domain_state_coarse_key`, and explicitly state that collisions do not prove duplicate records. A new test uses two records with different partner, indicator, trade flow, and valuation to verify that both records remain and only the coarse collision is reported.

**The revised metric is a screening signal, not a duplicate detector.** A future domain-aware identity contract must define the dimensions that make an IMF IMTS observation distinct before anyone can declare or deduplicate duplicate records. This requires a separate contract/adapter decision; it is not part of this repository-cleanup patch.

## 4. Integration consequence

- The WDI V2 output itself is present and contains 29,004 DomainState records, but its source extract has `available_at=null` and `source_revision=null`; point-in-time eligibility remains UNKNOWN.
- The six missing references prevent declaring the entire 21-asset registry complete.
- The corrected coarse-key diagnostic must be rerun on the PR head before treating its revised report as current.
- No missing experiment file is to be added or altered.
- WGI DomainState materialization remains unproven until its source ZIP can be supplied through a reproducible, hashed adapter run.

The Discovery code may be integrated as a candidate Engine 1 foundation only with these limitations stated. The registry does not pass completeness, Engine 1 is not frozen, and Engine 2 remains closed until the separate acceptance/freeze/handoff gate is satisfied.


## 5. Status after integration

The Discovery V1 implementation and registry validator were merged into `main-phase2` via PR #28. This does not convert the recorded audit readiness into PASS. The six missing references remain a declared registry blocker until a separate source-backed change resolves the WGI output and an explicit policy decision addresses the five immutable historical paths. No missing artifact has been recreated, and no file under `experiments/**` was altered.
