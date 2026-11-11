# PayLock Blind Identity Extraction — Pilot V1

## Status
Executed as a **documentation-derived, synthetic-to-the-minimum abstraction pilot** on 2026-11-11.
This is not a replay of raw runtime logs and is not an independent production test. The source corpus consists of the committed PayLock experiment reports and observed-behavior records listed below.

## Research question
Can a small rule miner recover a stable condition for issuance of the PayLock terminal proof (H1 / EXECUTION_PROVEN) from anonymized lifecycle observations, without being given the canonical rule?

## Source corpus
Repository: `uniqueteamyemen/paylock-core`
- `integration/experiments/medusa/MEDUSA_INTEGRATION_REPORT.md`
- `integration/experiments/stripe/stripe-subscriptions/OBSERVED_BEHAVIORS.md`
- `integration/experiments/stripe/digital-goods/OBSERVED_BEHAVIORS.md`
- `integration/experiments/vendure/OBSERVED_BEHAVIORS.md`

The reports describe the observations in the table below. They are not raw event exports. Stripe subscriptions and Stripe digital goods are separate integration scenarios but share the same PayLock implementation and therefore are not assumed to be statistically independent.

## Blind representation (sealed key)
The rule miner received only four Boolean inputs named A–D and target Y.

| Case | A | B | C | D | Y |
|---|---:|---:|---:|---:|---:|
| T1 | 1 | 0 | 0 | 0 | 0 |
| T2 | 1 | 1 | 1 | 0 | 1 |
| T3 | 1 | 1 | 0 | 1 | 0 |
| H1 | 1 | 1 | 1 | 0 | 1 |

H1 is held out from rule selection and used only for a minimal transfer check. The blind dataset is a deterministic abstraction of the documented cases, not raw source telemetry.

## Search procedure
- Enumerated every conjunction of 1–4 signed Boolean literals over A, B, C, D.
- Retained rules with zero classification errors on the three training rows.
- Ranked retained rules by ascending literal count.
- Evaluated the retained rules on the single held-out row.
- No parameters were tuned against the held-out row.

## Observed computational result
- Candidate conjunctions searched: 80 (all non-empty subsets of variables with both polarities).
- Rules consistent with all training rows: 10.
- Simplest retained rule: `C = 1`.
- Simplest rule classified the held-out case correctly.
- All 10 retained rules also classified the single held-out row correctly.

This is a **non-identification result**, not evidence that C alone is the true governing mechanism. The training sample is too small and too structurally restricted: A is always 1, and the holdout repeats the positive training configuration. Multiple distinct rules are observationally equivalent on these cases.

## Sealed interpretation key (opened after extraction)
- A = valid H0/session exists.
- B = provider_ack exists.
- C = user_unlock exists.
- D = cancellation exists.
- Y = H1 / EXECUTION_PROVEN is issued.

The candidate reference expression previously reconstructed from the protocol is:
`Y = A AND B AND C AND NOT D`.

The blind extraction did **not** uniquely recover this expression. It returned the simpler `C` rule because the evidence corpus contains no case where C=1 while another required condition is absent. It therefore cannot establish that A and B are necessary, or that D independently blocks issuance when C=1.

## What this pilot establishes
1. A small exhaustive Boolean search is executable against anonymized PayLock lifecycle abstractions.
2. The observed cases are consistent with the candidate four-condition rule.
3. The current evidence is insufficient to identify that rule uniquely.
4. The Vendure H1 issuance case transfers to the simplest extracted rule, but it is not a guarded external-execution holdout.
5. The Medusa report provides the clearest external deny/allow transition pair; the other integration records add lifecycle variation but do not supply all missing counterfactual combinations.

## What it does not establish
- No raw production logs were parsed.
- No fresh requests were sent to the PayLock Railway runtime.
- No Checkly run was triggered.
- No new Medusa/Vendure/Stripe runtime experiment was performed.
- No causal claim is made.
- No claim of statistical generalization is justified by one holdout.

## Required next evidence
To distinguish the four-condition rule from simpler alternatives, obtain or generate *observed* cases for:
- A=0 with B/C/D combinations controlled where the API permits.
- A=1, B=0, C=1, D=0.
- A=1, B=1, C=0, D=0.
- A=1, B=1, C=1, D=1.
- Duplicate/replay and timeout/rollback cases, with H1 and external execution outcomes recorded separately.

Each row must retain source reference, raw event sequence or request/response artifact, timestamp, environment, and outcome provenance. Do not synthesize missing observations and label them as measured.

## Provenance
- CHAOS base commit: `1bfc8cada347290859e939fd767e97044c302c1e`.
- This report is added on isolated branch `experiment/paylock-identity-blind-v1`; no default-branch files were changed.
- PayLock source corpus was read from its GitHub default branch during this run.
