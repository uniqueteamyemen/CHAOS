# Experiment B — stock identity on a seeded district network

Identity (zero parameters): `opening + arrivals - dispensed - expired = closing`.
Synthetic data: 3 districts × 24 months; leak of **90 units/month** in DIST-B from month 7.
Noise Gaussian(0, 2). σ is pooled over the declared quiet window (months 1–6), all districts: **σ = 2.16**, threshold 3σ = 6.48.

| district | first alarm | cumulative gap | closing (m24) | cover per records | true cover |
|---|---|---|---|---|---|
| DIST-A | — | -1.6 | 1882 | 4.65 mo | 4.65 mo |
| DIST-B | 9 | 1620.3 | 260 | 4.15 mo | 3.38 mo |
| DIST-C | — | -13.5 | 1894 | 4.68 mo | 4.68 mo |

## Events (one per breach episode)

| event | district | month | rate | cumulative | attributed | class |
|---|---|---|---|---|---|---|
| 8997e90ffbfedb2f | DIST-B | 9 | 92.0 u/mo | 274 | dispensed | missing_flow |

## CUSUM cross-check (first alarm only)

- DIST-A: first alarm month —, total crossings 0
- DIST-B: first alarm month 7, total crossings 18
- DIST-C: first alarm month —, total crossings 0

## What the experiment establishes

1. Alarm in **month 9** in DIST-B only. DIST-A and DIST-C stay silent for 24 months — a rule that never fires is useless, and a rule that fires everywhere is worse.
2. Detected rate **92.0 units/month** against a seeded truth of 90.
3. Attribution happened only because `arrivals_central_log` records the same term independently. Delete that column and the same event is emitted as `unresolved` — honest, but not actionable.
4. At the moment of detection the ledgers report **4.15 months** of cover; the identity reports **3.38**. The gap is **23 days** of runway, discovered in month 9 instead of at stock-out.
5. σ from six points is a fiction: the same window gave 0.73 per-district and 2.2 pooled. Pooled is the only defensible choice until the history is long.
