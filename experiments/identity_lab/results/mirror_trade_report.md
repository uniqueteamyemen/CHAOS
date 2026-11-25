# Experiment G — the edge identity on real official data

Eurostat Comext `ds-045409`, intra-EU goods, **2024 monthly, 6 country pairs, 12 directed edges**.
Each movement is declared twice: once by the exporter (FOB, flow 2) and once by the importer
(CIF, flow 1). Identity: `declared_out = declared_in`. Zero parameters.

## What the data says

| quantity | value |
|---|---|
| observations (edge-months) | 144 |
| directed edges | 12 |
| median abs relative gap, same month | **7.3%** |
| median abs gap, exporter month vs importer next month | **8.9%** |
| share above 5% tolerance, same month | 64% |
| share above tolerance, one-month shift | 74% |

## The finding, and it is not the one we wanted

On real data the raw edge residual is **large and systematic**, not zero. Two official records of
the same movement disagree by several percent, month after month, for every pair. The cause is
known and documented: exports are valued FOB and imports CIF, so freight and insurance are counted
on one side only; partner attribution and re-exports add more.

So the identity `declared_out = declared_in` **does not hold on real trade data**, and cannot be
used as a zero-parameter break detector unless the valuation basis is first reconciled. This is
the same lesson as the EIA crude series, but on edges: a constant offset is not a break, it is a
missing term in the identity.

## Does shifting one month help?

Median gap moves from 7.3% to 8.9%. No improvement: timing is not the dominant cause here.

## What is left after the known cause

The tail above the declared tolerance is what a real detector would chase — and it needs
adjudication, not a threshold. `exp_g_real/data/adjudication_ledger.csv` holds the 20 largest
edge-months with empty `human_label`, `reviewer`, `reviewed_at` columns: this is the twenty
incidents the previous phase said must be labelled by a human before any threshold is claimed
as calibrated.

## Honest boundary

- These are aggregate macro statistics, not warehouse ledgers: the 'units' are euros of goods.
- Six pairs, one year: enough to establish that the gap is systematic, not enough to estimate its
  distribution per corridor.
- No ground truth labels exist, so nothing here can be called a false alarm or a true one yet.
