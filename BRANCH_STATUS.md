# ⛔ BRANCH STATUS — AUTHORITATIVE REGISTER

**Repository:** `uniqueteamyemen/CHAOS`  
**Effective date:** 2026-11-25  
**Authority:** This file is subordinate to the current execution truth in `STATUS.md` and the explicit retired-branch register in Issue #52. If a conflict appears, `STATUS.md` and Issue #52 prevail until this file is corrected.

## ACTIVE — APPROVED WORK

| Branch | Status | Scope |
|---|---|---|
| `main-phase2` | ACTIVE — INTEGRATION BASELINE | Canonical repository baseline |
| `feat/p1-4-capability-envelope-pilot-v1-20261125` | ACTIVE WORK BRANCH | P1.4 capability-envelope pilot repair and Evidence Pipeline migration |

**Only the two branches above are authorized as current execution/integration targets.** The P1.4 branch is the active implementation branch. New implementation work must follow the current `STATUS.md` and the P1.4 capability-envelope contract/gates.

## RETIRED — DO NOT USE

The 18 branches explicitly listed in [Issue #52 — INACTIVE BRANCHES](https://github.com/uniqueteamyemen/CHAOS/issues/52) are retired and must not be checked out for new work, used as PR bases, continued, or merged.

In particular:

- `feat/p2b-five-detector-competition` — RETIRED. P2-B is completed and merged through PR #48. PR #49 was closed without merge. `STATUS.md` explicitly prohibits using this branch as an accepted base or source of results.
- `feat/p2-c-detector-batch-v1` — RETIRED / superseded draft.

## RETAINED FOR HISTORY OR REVIEW — NOT ACTIVE

These branches are preserved but are not authorized implementation targets:

| Branch | Status | Restriction |
|---|---|---|
| `feat/p1-4-capability-envelope-pilot-v1` | LEGACY HISTORY | Do not use as active work; use the dated P1.4 branch above |
| `feat/p2c-evidence-first-execution-v1` | REVIEW / MIGRATION SOURCE ONLY | Do not resume or merge directly; port required repairs to the active P1.4 branch and retest first |

Other branches not listed in ACTIVE are not approved execution targets. Their existence on GitHub does not imply authorization. Review and explicitly classify them before use.

## Mandatory execution rules

1. Read `STATUS.md` before any work; it governs the active phase, plan, and gates.
2. The active work branch is `feat/p1-4-capability-envelope-pilot-v1-20261125`, not any P2-B/P2-C predecessor.
3. Do not revive `feat/p2b-five-detector-competition`; P2-B is completed.
4. Do not resume `feat/p2c-evidence-first-execution-v1` directly. Port only validated required repairs into the active P1.4 branch and rerun the prescribed gates.
5. Keep branch history intact. This register does not claim to delete, rename, or technically lock Git refs.

## Technical limitation

This is a visible repository-level governance register, not a GitHub branch-protection mechanism. It does not technically prevent a user with write permission from pushing to or creating branches from other refs. GitHub rulesets/branch protection must be configured separately to enforce that restriction.

---
**Current authorization:** `main-phase2` (integration) and `feat/p1-4-capability-envelope-pilot-v1-20261125` (active P1.4 work) only.
