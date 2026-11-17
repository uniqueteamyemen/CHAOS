# Data sources, licenses, and attribution

This file is the source register for the automated real-data stress pipeline. Exact URLs,
collection timestamps, raw-file hashes, series counts, and coverage are written to the generated
`real_data_stress_pipeline/results/real_data_stress_manifest.json` and downloadable workflow
artifact for each run.

| Source | Intended use | Retrieval method | Rights / attribution |
|---|---|---|---|
| World Bank Commodity Markets / Pink Sheet | Monthly commodity prices (energy, metals, agriculture, food) | Official monthly historical XLSX discovered from the World Bank Commodity Markets page | The Pink Sheet page lists the monthly workbook, but this review has not established the workbook-specific redistribution license. Do not assume GEM's CC BY 4.0 license applies to Pink Sheet; verify its terms before redistributing raw data. |
| World Bank Global Economic Monitor (GEM) | Monthly CPI, industrial production, and selected trade indicators | World Bank Data API, source identifier 15; only monthly observations are accepted | Public World Bank DataBank source; apply the dataset's actual license and attribution shown by its metadata. The runtime records the API response and never assumes that annual data are monthly. |
| USGS ComCat / FDSN Event Web Service | Five predeclared tectonic-belt event catalogs and inter-event intervals | Official FDSN Event API, GeoJSON, yearly windows with adaptive subdivision | Attribute USGS/ComCat and contributing networks. Check event products and third-party contributions separately when used. |

## Source integrity rules

1. Permitted GEM and USGS raw API responses are saved unchanged under `artifacts/real_data_stress/raw/` and included in the restricted workflow artifact. The Pink Sheet workbook is fetched in memory only while its workbook-specific redistribution terms remain unverified; it is not saved, uploaded, or redistributed.
2. Each retained raw response receives SHA-256, retrieval timestamp, original URL, and query parameters. The Pink Sheet source receives a content SHA-256 and retrieval metadata without publishing the workbook or its underlying numeric observations.
3. A data revision is a new snapshot; previous snapshots are never overwritten in the artifact history. Derived Pink Sheet values are excluded from the public normalized input table until the source-specific redistribution terms are confirmed.
4. Missing values remain missing. No forward fill, interpolation, or synthetic padding is permitted.
5. A source is rejected from detector execution when period parsing, chronology, continuity, required point count, or robust-scale checks fail.
6. A manifest or catalog page alone is not treated as a raw dataset.
7. The detector's own `CONFIRMED` label is not independent confirmation of a real-world event.

## Coverage gate note

The World Bank Data Catalog currently describes GEM temporal coverage as 1990–2023. A complete monthly series over that period contains at most 408 observations. GEM may be included in the inventory and secondary 87-point cohort, but cannot pass the primary strict `n > 500` monthly gate unless the actual source data proves a longer history.

## Official references

- World Bank Commodity Markets: https://www.worldbank.org/en/research/commodity-markets
- World Bank Commodity Price Data catalogue: https://datacatalog.worldbank.org/search/dataset/0038238/commodity-prices-history-and-projections
- World Bank Global Economic Monitor: https://databank.worldbank.org/source/global-economic-monitor
- World Bank Data API documentation: https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures
- USGS FDSN Event API documentation: https://earthquake.usgs.gov/fdsnws/event/1/
