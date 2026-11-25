# ⛔ BRANCH STATUS — CENTRAL REGISTER

**Repository:** `uniqueteamyemen/CHAOS`  
**Effective date:** 2026-11-25  
**Purpose:** Prevent accidental continuation of stale or superseded work without requiring anyone to inspect individual branch contents.

## Authoritative status rule

A branch is **NOT an active execution target** unless it is explicitly listed under **ACTIVE** below. All other non-default branches are **INACTIVE / UNCLASSIFIED — DO NOT CONTINUE OR MERGE** until they are reviewed and explicitly reactivated here.

This is a repository-level status register. It does not delete branches, rewrite their commits, or claim that GitHub's branch list itself has been renamed or tagged.

## ACTIVE

| Branch | Status | Scope |
|---|---|---|
| `main-phase2` | ACTIVE | Repository integration/default branch |
| `feat/p2b-five-detector-competition` | ACTIVE WORK TARGET | Current P2-B detector competition work |

## INACTIVE / NOT AUTHORIZED FOR CONTINUATION

Every other branch currently present in this repository is retained for historical evidence and recovery, but is not an approved execution target. Do not base new work on it, merge it, or treat it as current without an explicit status change in this file.

## Reactivation procedure

1. Review the branch against the current CHAOS execution plan and the current `main-phase2` baseline.
2. Verify its latest commit, open pull requests, CI evidence, and whether its work is already superseded or merged.
3. Change this register explicitly: move the branch into **ACTIVE** and record its purpose and review date.
4. Do not reactivate a branch merely because it still exists on GitHub.

## Safety guarantees

- No branch is deleted by this register.
- No commit history is rewritten.
- `main-phase2` remains the default integration baseline.
- `A_FAST` and `A_CONSENSUS` baselines are not modified by this administrative action.
- This file is the central status source; branch existence alone does not imply activity.

---
**Administrative status:** INACTIVE BY DEFAULT unless allowlisted above.
