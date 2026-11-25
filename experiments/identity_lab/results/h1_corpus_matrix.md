# Experiment A4 — auditing the corpus as traces

The reports were encoded as traces and audited. Every step carries its provenance,
and no invariant may claim support from an inferred step.

| trace | variant | observed | stated | inferred | steps |
|---|---|---|---|---|---|
| medusa | signal_based | 7 | 3 | 0 | 10 |
| stripe_subscriptions | receipt_bound | 3 | 6 | 0 | 9 |
| stripe_digital | signal_based | 0 | 4 | 0 | 4 |
| vendure | unknown | 1 | 2 | 0 | 3 |

## Invariant matrix

| invariant | medusa | stripe_subscriptions | stripe_digital | vendure |
|---|---|---|---|---|
| I1 one completion | — | HOLDS (observed) | — | — |
| I2 proof before unlock | HOLDS (observed) | HOLDS (stated) | HOLDS (stated) | HOLDS (stated) |
| I3 closure after cancel | — | HOLDS (stated) | — | — |
| I4 role of acknowledgement | VARIANT (observed) | HOLDS* (stated) | VARIANT (stated) | HOLDS* (stated) |
| I5 attributed refusals | HOLDS (observed) | HOLDS (observed) | — | — |

## What each cell rests on

### medusa — `integration/experiments/medusa/MEDUSA_INTEGRATION_REPORT.md`
- **I1** untested: no replay attempt recorded *(provenance: —)*
- **I2** holds: ack at step 4 precedes unlock 5 *(provenance: observed)*
- **I3** untested: no cancellation in this run *(provenance: —)*
- **I4** variant: signal_based: ack is a precondition, not informational *(provenance: observed)*
- **I5** holds: 4/4 refusals carry a stated reason *(provenance: observed)*

### stripe_subscriptions — `integration/experiments/stripe/stripe-subscriptions/OBSERVED_BEHAVIORS.md`
- **I1** holds: replay rejected (409) *(provenance: observed)*
- **I2** holds: ack at step 2 precedes unlock 3 *(provenance: stated)*
- **I3** holds: post-cancel attempts rejected *(provenance: stated)*
- **I4** holdable: receipt_bound: ack present and uncoupled from unlock *(provenance: stated)*
- **I5** holds: 4/4 refusals carry a stated reason *(provenance: observed)*

### stripe_digital — `integration/experiments/stripe/digital-goods/OBSERVED_BEHAVIORS.md`
- **I1** untested: no replay attempt recorded *(provenance: —)*
- **I2** holds: ack at step 2 precedes unlock 3 *(provenance: stated)*
- **I3** untested: no cancellation in this run *(provenance: —)*
- **I4** variant: signal_based: ack is a precondition, not informational *(provenance: stated)*
- **I5** untested: no refusals *(provenance: —)*

### vendure — `integration/experiments/vendure/OBSERVED_BEHAVIORS.md`
- **I1** untested: no replay attempt recorded *(provenance: —)*
- **I2** holds: ack at step 2 precedes unlock 3 *(provenance: stated)*
- **I3** untested: no cancellation in this run *(provenance: —)*
- **I4** holdable: receipt_bound: ack present and uncoupled from unlock *(provenance: stated)*
- **I5** untested: no refusals *(provenance: —)*

## The reading

- **I1 and I3 rest on one source only**: stripe-subscriptions. No other run tried a replay,
  and no other run tried a completion after cancellation. One integration carrying an
  invariant is evidence, not proof — and it is the *same* implementation in all four runs,
  so the four traces are not four independent tests.
- **I2 is confirmed in medusa** by an explicit 400 before proof and a 200 after it. That is the
  strongest single observation in the entire corpus: the same transition class denied then allowed.
- **I4 is not an invariant at all** — it is a variant switch. In the evidence package the ack is
  informational; in both Stripe runs it is a precondition. An identity that flips between runs
  must record `identity_variant` with every event, or its events cannot be compared across time.
- **I5 holds where it was recorded**, but unevenly: medusa names every refusal with a code,
  stripe-sub gives reasons without codes, and vendure records none.
- **Vendure contributes almost nothing to the gate** — three steps, one code, and its own report
  says the deny/allow pair was never observed.
