# Official catalog verification notes — 2026-08-26

## World Bank WDI

Official page: https://datatopics.worldbank.org/world-development-indicators/

The page describes WDI as the World Bank's compilation of cross-country comparable development data. It states that the database contains approximately 1,400 time-series indicators for 217 economies and more than 40 country groups, with many series extending more than 50 years. It explicitly exposes bulk Excel and CSV downloads including metadata, and states that the files are revised when WDI is updated. The page also lists themes covering poverty/inequality, people, environment, economy, states/markets, and global links.

Local evidence already profiled in `workbook_profile.json` and `catalog_metadata_extract.json` is more precise for the downloaded vintage: 1,498 series metadata rows, 264 country/aggregate rows, annual observation columns 1960–2025, 396,970 observation rows, and license distribution of 1,495 `CC BY-4.0` series plus 3 `CC BY 3.0 IGO` series.

## IMF WEO

Official page: https://data.imf.org/en/datasets/IMF.RES:WEO

The April 2026 WEO page states that WEO is published twice yearly in April and October. It covers selected national accounts, inflation, unemployment, balance of payments, fiscal indicators, trade, country/country-group aggregates, and commodity prices. It states that data are available from 1980 to the present and that projections are provided for most series for the next five years, while some country/indicator years are incomplete or unavailable. The page exposes the April 2026 entire Excel dataset, a vintage-specific appendix, and a WEO Historical Forecasts Database.

Local evidence already profiled in `workbook_profile.json` and `catalog_metadata_extract.json`: `WEOApr2026all.xlsx` has Countries 8,668 rows × 81 columns, Country Groups 689 × 81, Commodity Prices 75 × 81, and Country Group Composition 626 × 6; current-vintage columns reach 2031. `WEOhistorical.xlsx` has 8,844 rows × 77 columns for each of `ngdp_rpch`, `pcpi_pch`, and `bca_gdp_bp6`, with Spring/Fall vintage columns from 1990 through 2026. Its local Info text warns that WEO historical data are updated continually, may use splicing and staff estimates, and can differ from other official sources; usage points to IMF copyright and usage terms.

These are factual catalog/provenance notes only. No experiment was run and no architecture or safety gate was changed.

## UCDP

Official page: https://ucdp.uu.se/downloads/

The UCDP Download Center states that current datasets are free downloads, include codebooks and where available version histories, and are licensed under `CC BY 4.0` subject to citation. It lists GED Global version 26.1 as disaggregated event data with events geocoded to individual villages and durations disaggregated to individual days. It lists UCDP/PRIO Armed Conflict version 26.1 as a conflict-year dataset covering 1946–2025, and also lists the UCDP Country-Year Dataset on Organized Violence within Country Borders version 26.1 as an aggregation based on GED for the post-1989 period. The center also lists other annual/dyadic/actor/protest datasets and a programmatic API.

Local downloaded assets: `raw/ucdp/ged261-csv.zip` and `raw/ucdp/ucdp-prio-acd-261-csv.zip`; staged profiles are `staged/ucdp/ged261/GEDEvent_v26_1.csv` (417,968 rows, 49 columns, 1989–2025) and `staged/ucdp/prio261/UcdpPrioConflict_v26_1.csv` (2,816 rows, 28 columns, 1946–2025). The source event/article fields and uncertainty/death fields are retained.

## EIA

Official page: https://www.eia.gov/opendata/index.php#bulk-downloads

The EIA Open Data page states that EIA provides free and open data through its API and open data tools, organized into energy time-series datasets including petroleum, natural gas, electricity, coal, total energy, CO2 emissions, and international energy. It states that API bulk downloads are updated twice daily and that data should be used in compliance with EIA's copyrights and reuse policy.

Local downloaded asset: `raw/eia/INTL.zip` (24,126,861 bytes), staged as `staged/eia/intl/INTL.txt` (128,747,528 bytes JSONL). The local profile reports 104,407 series objects and 232 category objects; 100,459 annual, 2,159 monthly, and 1,789 quarterly series objects; series metadata spans 1949–2026. Raw and staged files remain separate; no series were averaged or reconciled.

## Data Readiness Gate gap verification

UCDP official download center confirms `UCDP Country-Year Dataset on Organized Violence within Country Borders version 26.1` is available as CSV, Excel and codebook. It is described as an accurate country-year aggregation based on UCDP GED for post-1989 organized violence. The source page identifies the required citation and the download center's general CC BY 4.0 terms remain applicable.

NOAA NCEI's official catalog exposes `Global Summary of the Month (GSOM)` as a separate monthly product. This gate will use an original monthly GSOM file with an explicit station/period scope rather than converting the already downloaded GHCN-Daily station files to annual values. The earlier official notes record GSOM v1 as monthly, 1763–present, with temperature/precipitation/snowfall/degree-day/event-count elements, CSV distribution, weekly updates and DOI 10.7289/V5QV3JJ5. No daily-to-annual conversion is permitted in this gap-filling task.

## NOAA GSOM official metadata verification

Official metadata page: https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00946

The page identifies Global Summary of the Month (GSOM), Version 1, as a monthly-resolution product from 1763 to present, updated weekly. It lists monthly mean maximum/minimum/mean temperatures, monthly total precipitation and snowfall, departures from normal, degree days, threshold-day counts, extremes, fog and thunderstorm counts. It says the primary input is GHCN-Daily, provides direct download links and CSV format, and distinguishes GSOM from GHCN-Monthly and legacy U.S. COOP summaries. The page gives DOI `10.7289/V5QV3JJ5`, time interval `1763-01-01 to Present` at one-month resolution, global spatial bounds, and a GSOM documentation PDF.

The gap-fill scope uses the original monthly `PRCP` column in nine explicitly selected station files under `raw/noaa/gsom_monthly/stations/`; it does not aggregate the GHCN-Daily files and does not create annual environmental values.
