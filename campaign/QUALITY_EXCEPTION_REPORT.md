# Quality & Exception Report

## Campaign status

This report covers the first bounded acquisition run performed in the isolated campaign workspace. It is not a claim that the 25-year, nine-source acquisition is complete. The report distinguishes observed raw payloads, metadata probes, access exceptions, and sources that still require credentials or a scoped extraction plan.

The governing policy is that raw payloads are immutable, no raw imputation is performed, and conflicting source values are not averaged or arbitrated at ingestion time.

## Observed raw payloads

| Source | Raw material captured | Window or scope | Status |
|---|---|---|---|
| IMF DataMapper | `NGDP_RPCH` JSON payload | 1980–2025 historical years retained in the derived coverage view; forecasts remain in raw | Observed payload |
| USGS NWIS | Daily discharge series for site `01646500`, parameter `00060` | 2000-01-01–2025-12-31 | Observed payload |
| World Bank WDI | World aggregate GDP at constant USD, `NY.GDP.MKTP.KD` | 2000–2025 | Observed payload |
| UN Comtrade | Public preview, Australia, 2022, imports, TOTAL commodity | Single annual probe | Observed payload; not a 25-year extract |
| GDELT | `lastupdate.txt` manifest | Current metadata probe | Metadata only |
| EIA | API root response | Current metadata probe | Metadata only |

## Exceptions and unresolved access

| Source | Exception | What was not done | Next controlled action |
|---|---|---|---|
| FRED | Direct FRED-MD URLs returned HTTP 403 | No observations were inferred and no substitute values were created | Obtain/use an approved FRED API key or approved archive path; preserve vintages |
| NOAA NCEI | API and archive attempts failed from the collection environment with timeout/TLS errors | No weather observations were fabricated or interpolated | Retry through an approved NOAA access route and record dataset/station/product version |
| ACLED | Access is account/API dependent | No data was collected without credentials | Obtain authorized access and record endpoint/query/version |
| UCDP | API requires a token request and versioned access | No data was collected without a token | Request a token; use a fixed dataset version and page through results |
| EM-DAT | Public portal requires registration and has documented legal/methodological conditions | No data was collected without confirmed access terms | Confirm account and permitted use before extraction |
| EIA | API root was reachable, but scoped series require a route and API key | No broad series collection was attempted | Select bounded energy routes and use a registered key |
| GDELT | Full raw archives are very large | No whole-database download was attempted | Use bounded event queries/BigQuery or date-partitioned downloads |

## Data policy checks

| Check | Result |
|---|---|
| Raw payload retained | Passed for every successful probe |
| Request URL retained | Passed for bounded collection runs |
| SHA-256 recorded | Passed for captured raw files |
| Raw imputation | Not performed |
| Source reconciliation | Not performed |
| Forced averaging of conflicts | Not performed |
| Historical forecasts mixed into derived historical coverage | Prevented for IMF coverage view; raw forecast payload remains preserved |
| Native source resolution destroyed | Not performed |
| Missing interval invented | Not performed |

## Interpretation

The first run proves that the collection workspace can preserve real source responses and record access failures without silently replacing them. It does not yet establish full coverage for every selected source, and the current coverage matrix must therefore be read as a coverage baseline and exception register, not as a completed historical database.

## Subsequent bounded collection runs

Additional bounded runs were captured after the initial probes. World Bank WDI `NY.GDP.MKTP.KD` for `WLD` (2000–2025) and a UN Comtrade public preview for Australia 2022 were captured as raw JSON with request files and SHA-256 records. Four attempted GDELT daily archive paths returned HTTP 404 and were recorded as exceptions without zero-byte payloads. NOAA archive attempts produced a TLS/SSL connection failure and were recorded as an exception without substitute observations.

The current derived coverage matrix contains seven rows representing observed payloads, metadata probes, and access exceptions. It must not be interpreted as complete 25-year coverage for all sources; it is the first executable acquisition baseline and exception register.

## Integrity verification

The final integrity check found 33 non-empty raw/request/exception files in the raw store, 12 rows in the current variable-level coverage matrix, and no source reconciliation or raw imputation operation. The presence of words such as interpolation or imputation in this report reflects prohibitions and audit statements, not executed transformations. The raw store manifest was regenerated after the latest collection runs.
