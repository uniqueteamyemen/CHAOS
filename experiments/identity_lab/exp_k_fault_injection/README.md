# Experiment L — Controlled ERP fault-injection stress test

## Classification

This is a **synthetic stress test**, not real-world validation and not a substitute for an operational ERP export. The baseline is an Odoo-export-shaped fixture generated deterministically in code; it is not claimed to have been produced by a running Odoo instance.

## Why it exists

A clean ERP workflow generally records linked documents consistently. Testing only that clean path does not exercise the ambiguity and missing-evidence states. Experiment L preserves a clean baseline, hashes it, mutates only a deep copy, and records every mutation in a manifest.

## Scenario

Default run: 100 shipments and 100 independent receiver records.

- 10%: remove the receiver record → expected `unmatched`.
- 10%: remove the explicit shipment link and create a duplicate plausible receipt → expected `ambiguous`.
- 10%: remove the explicit link and shift the receipt beyond the configured 3-day matching window → expected `unmatched`.
- Remaining 70%: unchanged exact matches.

The percentages and random seed are parameters. Selection is deterministic for a given seed and fault-rate configuration. The three fault groups are disjoint.

## Separate semantic controls

Unit tests also verify:
- one approximate unique receipt remains unconfirmed;
- an explicitly linked receipt arriving after the time window remains an exact identity match but is classified as delayed;
- a quantity difference on an exact, provenance-complete receipt can produce a loss event;
- unconfirmed/ambiguous/unmatched candidates never produce a loss event.

## Integrity controls

- Clean baseline SHA-256 recorded before injection.
- Faults are applied to a deep copy; the clean baseline hash is checked afterward.
- Every injected change is recorded with target shipment and operation.
- No injected data is mixed into an operational dataset.
- No detection-rate or real-world accuracy claim is made.

## Run

```bash
python -m unittest experiments.identity_lab.exp_k_fault_injection.test_fault_injection -v
python -m experiments.identity_lab.exp_k_fault_injection.run_experiment
```
