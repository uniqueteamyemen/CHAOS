# Experiment L — an ERP-clean ledger under declared fault injection

200 transfers per run, 20 seeds. 15% carry a real short-shipment.

| | clean ERP | stressed |
|---|---|---|
| state accuracy | 100.0% | **97.0%** |
| true losses (mean) | 31.1 | 19.2 |
| missed losses | 0.0 | **11.8** |
| false-positive losses | 0.0 | **0.0** |
| loss precision | 1.0 | 1.0 |
| loss recall | 1.0 | 0.6253 |

## States under stress (mean per run)

| confirmed | candidate | ambiguous | unmatched |
|---|---|---|---|
| 128.0 | 20.4 | 15.9 | 35.8 |

## The point of the exercise

On clean ERP output everything is `confirmed`, and that number is worthless: the generator
made the documents agree. Under injected faults the matcher still separates the three states,
never converts an unmatched or ambiguous case into a confirmed loss, and the losses it misses
are exactly the ones it refused to guess about.

Which is the honest reading: **precision is protected, recall pays for it.** A real deployment
must decide how much recall to buy back, and that decision belongs to the operator, not to the
matcher.
