# Experiment I — the fixture cycle, on the platform's own module

Run `fx-2025-10-01-audit`: five events seeded, one of them the forbidden duplicate confirmation.

| step | result |
|---|---|
| seeded events | 5 |
| violations found by the auditor | 1 |
| events visible to users after seeding | **1** (the real one only) |
| purge | removed 5 events and 5 keys |
| stream size after purge | 1 |
| real event survived | **True** |

## The residual event

The violation is not logged as a note: it becomes the lab's object, with the same fields as
every other break — identity id, attributed term, classification, adjudication, evidence.

| event | identity | magnitude | attributed | class |
|---|---|---|---|---|
| 4f803fd6230a4ca8 | PHARMA_SINGLE_CONFIRMATION_V1 | 1 excess_confirmation | match_confirmation | control_violation |

Schema problems: none.

## What this proves, and what it does not

- Proves: the platform can express the violation, hide it from users, and remove it exactly.
- Proves: the same event shape feeds the detector without translation loss.
- Does not prove: any detection rate. The fault was seeded by us; this is plumbing, not performance.

## The identity

> one request may be confirmed once

The same statement as *one session may produce one H1* — which is why the second confirmation
is a break and not a duplicate, and why the same auditor can read both systems.
