# Data sources, licenses, and attribution

This file is the source register for the automated real-data stress pipeline. Exact URLs,
collection timestamps, raw-file hashes, series counts, and coverage are written to the generated
`real_data_stress_pipeline/results/real_data_stress_manifest.json` and downloadable workflow
artifact for each run.

| Source | Intended use | Retrieval method | Rights / attribution |
|---|---|---|---|
| World Bank Commodity Markets / Pink Sheet | Monthly commodity prices (energy, metals, agriculture, food) | Official monthly historical XLSX discovered from the World Bank Commodity Markets page | World Bank Commodity Price Data catalogue identifies CC BY 4.0; cite the World Bank and preserve source/version metadata. |
| World Bank Global Economic Monitor (GEM) | Monthly CPI, industrial production, and selected trade indicators | World Bank Data API, source identifier 15; only monthly observations are accepted | Public World Bank DataBank source; apply the dataset's actual license and attribution shown by its metadata. The runtime records the API response and never assumes that annual data are monthly. |
| USGS ComCat / FDSN Event Web Service | Five predeclared tectonic-belt event catalogs and inter-event intervals | Official FDSN Event API, GeoJSON, yearly windows with adaptive subdivision | Attribute USGS/ComCat and contributing networks. Check event products and third-party contributions separately when used. |

## Source integrity rules

1. Raw responses are saved unchanged under `artifacts/real_data_stress/raw/` and included in the workflow artifact.
2. Each saved response receives SHA-256, retrieval timestamp, original URL, and query parameters.
3. A data revision is a new snapshot; previous snapshots are never overwritten in the artifact history.
4. Missing values remain missing. No forward fill, interpolation, or synthetic padding is permitted.
5. A source is rejected from detector execution when period parsing, chronology, continuity, required point count, or robust-scale checks fail.
6. A manifest or catalog page alone is not treated as a raw dataset.
7. The detector's own `CONFIRMED` label is not independent confirmation of a real-world event.

## Official references

- World Bank Commodity Markets: https://www.worldbank.org/en/research/commodity-markets
- World Bank Commodity Price Data catalogue: https://datacatalog.worldbank.org/search/dataset/0038238/commodity-prices-history-and-projections
- World Bank Global Economic Monitor: https://databank.worldbank.org/source/global-economic-monitor
- World Bank Data API documentation: https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures
- USGS FDSN Event API documentation: https://earthquake.usgs.gov/fdsnws/event/1/
