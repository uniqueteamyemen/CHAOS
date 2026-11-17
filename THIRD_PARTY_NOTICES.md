# Third-Party Notices and Data Rights Register

This register distinguishes original CHAOS materials from external data and software. The root `LICENSE` applies only to original project materials controlled by the CHAOS rights holder. It does not relicense or claim ownership of external content.

## 1. Data sources planned for the Phase 2 stress pipeline

| Provider / source | Official source | Known rights / metadata | Handling rule |
|---|---|---|---|
| World Bank Pink Sheet — `CMO-Historical-Data-Monthly.xlsx` | [World Bank Pink Sheet page](https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/world-bank-commodities-price-data-the-pink-sheet) | The page lists the monthly historical workbook as a related file. This review did not establish a workbook-specific redistribution license. Do not assume GEM's CC BY license applies to Pink Sheet. | Fetch for analysis; retain retrieval time and SHA-256; do not commit or redistribute the raw workbook until its specific terms are verified. |
| World Bank Global Economic Monitor (GEM) | [World Bank Data Catalog — GEM](https://datacatalog.worldbank.org/infrastructure-data/search/dataset/0037798/global-economic-monitor) | Catalog metadata identifies the dataset as Public and Creative Commons Attribution 4.0 (CC BY 4.0). Catalog metadata reports 1990–2023 coverage and monthly and/or quarterly and annual periodicities. Preserve attribution and indicate modifications. | Preserve version/update date, archive hash, source metadata, attribution, and transformations. Apply the strict >500 monthly-observation gate to actual series; the published coverage alone implies no more than 408 calendar months in 1990–2023. |
| USGS Earthquake Catalog / FDSN Event Web Service | [USGS FDSN API](https://earthquake.usgs.gov/fdsnws/event/1/) and [USGS Data Licensing](https://www.usgs.gov/data-management/data-licensing) | USGS-authored/produced information is generally U.S. public domain. Non-USGS photographs, partner/contributor data, or other third-party material may have separate restrictions. USGS requests source attribution. | Preserve exact query parameters, retrieval timestamp, API version, event IDs, contributor/catalog metadata, raw response hash, and attribution. Inspect each selected product for third-party exceptions. |

## 2. Software dependencies

The Phase 2 pipeline must maintain a resolved dependency manifest containing exact versions, package URLs, license identifiers, and lockfile SHA-256. The current CI requirements pin `statsmodels==0.15.0`; NumPy and openpyxl are bounded by compatible version ranges. The initial dependency candidates are:

- Python standard library.
- `requests` for retrying HTTP retrieval.
- `openpyxl` for workbook inspection.
- `numpy` for numeric transforms and detector inputs.
- `statsmodels==0.15.0` for ADF and KPSS stationarity diagnostics (BSD-3-Clause).
- `pytest` for tests.

This is a candidate list, not a statement that all packages have already been installed or validated. The CI-generated dependency manifest must record the packages actually used.

## 3. Attribution and redistribution rules

1. Preserve source name, official URL, retrieval timestamp, source update/vintage, query parameters, coverage window, and SHA-256 for every input.
2. Preserve provider attribution in reports and artifacts.
3. Identify transformed values and derived tables as CHAOS-generated outputs; do not imply provider endorsement.
4. Do not redistribute raw files while their terms are unclear or prohibit redistribution. In that case, keep them in the execution environment and publish only permitted manifests, checksums, and derived results.
5. A publicly accessible URL is not, by itself, permission to redistribute or commercially exploit the retrieved file.
6. The proprietary CHAOS `LICENSE` does not override external terms.

## 4. Review status

The rights position of each downloaded version must be rechecked before public redistribution or commercial deployment. This register is a compliance record, not legal advice.