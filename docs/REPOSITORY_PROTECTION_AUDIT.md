# CHAOS Repository Protection Audit

**Audit date:** 17 November 2026  
**Repository:** `uniqueteamyemen/CHAOS`  
**Branch reviewed:** `main-phase2`  
**Branch head at verification:** `f3215a6ffb750c273b8e4898a56c2483613b660c`

## 1. Current observed GitHub state

The branch endpoint reports:

- `protected: true`
- Branch head `69320401e2ac73c6ded1b313022b6584c81c645f`
- Classic protection object `enabled: false` (the active protection is through a repository ruleset)

Repository ruleset `27488330` is active and explicitly targets `refs/heads/main-phase2`.

| Rule | Current value |
|---|---|
| Enforcement | `active` |
| Target pattern | `refs/heads/main-phase2` |
| Prevent deletion | Enabled |
| Prevent non-fast-forward updates | Enabled |
| Required status check | `stress` (GitHub Actions integration ID 15368) |
| Restrict updates | Enabled |
| Strict status-check policy | `false` |
| Require pull requests | Not configured |
| Required human approvals | Not configured |
| Bypass | Repository role and integration actors are listed; `current_user_can_bypass: always` |

**Conclusion:** `main-phase2` is protected by an active matching ruleset. The ruleset is not an administrator-proof lock: configured bypass actors, including repository roles, can bypass. It also does not force changes through pull requests or require independent human review. The current required check is the single job context `stress`.

The ruleset details were re-read from GitHub after the owner-side settings changed. The connected GitHub integration still does not expose a ruleset mutation action, so no claim is made that this assistant created or edited the platform settings.

## 2. Workflow conflict and remediation

The previous workflow attempted to push generated results directly to `main-phase2` before its own `stress` job had completed. That is incompatible with the newly active `update` and `required_status_checks` rules for a non-bypass automation actor.

The P2.2 workflow was changed so generated results remain in the workflow workspace/artifact and are attached to a new P2.2.1 GitHub Release. The workflow tags its source commit and does not push generated output commits to the protected branch. The validation run is:

[GitHub Actions — P2.2.1 validation](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44164671959)

At the time of this audit, the full historical pipeline was still running; release publication is not considered complete until the workflow reports success and the release/tag assets are verified.

## 3. Tag protection remains outstanding

No tag-targeted ruleset was verified for:

- `phase1-detector-freeze-v1.0`
- `p2.2-historical-stress-v1.0.0`

The Phase 1 Release API reports `immutable: false`. These releases and tags must not be described as immutable or platform-locked. A separate tag ruleset should match those exact tag refs and prevent update/deletion.

## 4. Frozen-source protections

The existing `.github/workflows/experiments-immutable.yml` checks changes to `experiments/**` on pull requests and direct pushes. `AGENTS.md` also forbids edits to the frozen experiments archive and `structural_engine/isolated_break_detector_v1/` in this workstream.

The current code changes are confined to:

- `real_data_stress_pipeline/run_pipeline.py`
- `real_data_stress_pipeline/tests/test_pipeline.py`
- `.github/workflows/real-data-stress.yml`
- Documentation and generated P2.2 reporting

No change was made to `experiments/**`, the frozen detector implementation, or its constants.

## 5. Evidence

- [Branch metadata](https://github.com/uniqueteamyemen/CHAOS/tree/main-phase2)
- [Ruleset 27488330](https://github.com/uniqueteamyemen/CHAOS/rules/27488330)
- [Updated P2.2 workflow](../.github/workflows/real-data-stress.yml)
- [P2.2.1 validation run](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44164220182)
- [Archive and tag status](ARCHIVE_AND_TAG_STATUS.md)
