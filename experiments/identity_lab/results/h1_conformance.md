# Experiment A — H1 identity, executable

Assertions replayed against the zero-parameter machine: **18/18 PASS**.

| test | expected | observed | result |
|---|---|---|---|
| health | 200 | 200 | PASS |
| session_success | 200 | 200 | PASS |
| duplicate_payment_intent | 409 | 409 | PASS |
| payment_attestation | 200 | 200 | PASS |
| duplicate_receipt | 409 | 409 | PASS |
| provider_ack | 200 | 200 | PASS |
| provider_ack_replay | 200 | 200 | PASS |
| invalid_receipt_missing | 400 | 400 | PASS |
| tampered_receipt_mismatch | 409 | 409 | PASS |
| user_unlock | 200 | 200 | PASS |
| resolve_idempotent | 200 | 200 | PASS |
| unlock_replay | 409 | 409 | PASS |
| session_cancel | 200 | 200 | PASS |
| payment_cancel | 200 | 200 | PASS |
| unlock_after_cancel | 409 | 409 | PASS |
| resolve_after_cancel | 409 | 409 | PASS |
| unknown_h0_webhook | 404 | 404 | PASS |
| create_negative_intent | 200 | 200 | PASS |

## Violation injection

A second completion was allowed on purpose. The auditor produced **2 residual events**, schema problems: none.

| event | time | magnitude | attributed term | class |
|---|---|---|---|---|
| a9daf29c03dc7f92 | step:3 | 1 excess_completion | unlock_path | control_violation |
| 6c27d7629b549b7a | step:4 | 1 state_change | ack_path | control_violation |

## What this fixes

The identity is not a model of PayLock: it is the set of statements that must be true for
the service to be PayLock. A trace — ours or the service's own log — is enough to audit it,
with no configuration, no parameters, and no access to the private code.

The experiment also forced a schema change: `control_violation` did not exist and was added
to `classification`, because a single-occurrence identity fails by *control*, not by a missing flow.
