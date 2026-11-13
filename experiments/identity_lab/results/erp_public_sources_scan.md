# Public ERP / logistics source scan — Experiment J

**Question:** locate downloadable operational movement data with an independent receiving record, not merely an outbound quantity or an inventory snapshot.

## Best structural fit: OpenBoxes

- Official stock-movement workflow distinguishes outbound shipment from inbound receipt. The receiving facility enters the quantity actually received and records short shipments/damage; the workflow supports partial receipts.
- The Transaction Report exports opening inventory, ins, outs, adjustments and closing inventory by product/location.
- The application offers demo-data loading, but demo data is not evidence of real-world operations. A real OpenBoxes tenant export, supplied by an authorized operator, is the strongest schema-level candidate found in this scan.
- Evidence: https://openboxes.com/docs/openboxes-guide/stock-movements/ ; https://help.openboxes.com/article/48-receiving ; https://help.openboxes.com/article/85-transaction-report ; https://help.openboxes.com/article/62-load-demo-data

**Assessment:** excellent for the required independent shipment/receipt workflow; actual operational status depends on obtaining a real tenant export. Do not label loaded demo data as real validation.

## Real operational report, access-controlled: Walmart Fulfillment Services

WFS documents an Inbound Receipts report that compares expected units with units checked in, received, and damaged. This is directly relevant to comparing dispatch/expected quantities with receiving evidence, but it is downloaded inside Seller Center by an authorized seller; it is not an open public corpus.

Evidence: https://marketplacelearn.walmart.com/ca/guides/Walmart%20Fulfillment%20Services%20%28WFS%29/Reports/wfs-reports---inbound-receipts

**Assessment:** strong real-world receipt evidence if an eligible seller can export it and retain the source shipment identifiers and provenance.

## Public research dataset candidate: Mendeley Warehouse Distribution System

The public record describes Jan–Jun 2023 shipping/distribution data, item and warehouse/sorting-facility information, and collection from historical records, shipping manifests and existing databases. It is CC BY 4.0.

Evidence: https://data.mendeley.com/datasets/z3xfgnnfmk/1

**Assessment:** downloadable research candidate, but the landing page does not establish that it contains a separate receiving-side record, actual received quantity, or a stable shared shipment key. Inspect the downloaded files before accepting it for D3. It may still support movement/time-pattern analysis.

## Additional candidate: Accenture Supply Chain Resilience Challenge (Kaggle)

The challenge describes transactional inbound/outbound shipment records and route/port/hub/customer context.

Evidence: https://www.kaggle.com/competitions/datathon-2022-upc-accenture/data

**Assessment:** candidate for shipment-flow and temporal analysis. The accessible dataset description did not establish independent receiving quantities or a shared sender/receiver key, so it is not yet qualified for D3.

## Explicitly excluded from real validation

The Analytics Engineering Inventory & Supply Chain dataset advertises paired transfers, partial receipts and opening balances, but explicitly describes itself as synthetic.

Evidence: https://www.analyticsengineering.com/datasets/inventory-supply-chain

**Assessment:** useful as a labelled plumbing fixture only; not a real operational validation corpus.

## Decision from this scan

No open, downloadable source was verified from its public documentation alone as both (a) actual operational records and (b) independently recorded dispatch and receipt quantities linked to the same physical transfer.

The shortest practical route is:
1. Request an authorized real-tenant OpenBoxes export or an actual WFS Inbound Receipts export, including original shipment/receipt identifiers and source timestamps.
2. In parallel, download and inspect the Mendeley files; accept them for D3 only if the files prove separate receipt observations and a defensible link key.
3. Use the Kaggle challenge data for movement/time analysis only unless inspection proves the missing receipt-side evidence.

Do not fill missing identifiers or receipt quantities synthetically. Preserve source files and hashes before normalization.
