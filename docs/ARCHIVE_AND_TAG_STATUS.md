# Phase 1 Archive and Tag Status

**Verification date:** 17 November 2026  
**Canonical Phase 1 commit:** `51e4278309b7d32917b85903323a63f81d9e9b6a`

## Verified references

| Reference | Target | Status |
|---|---|---|
| `phase1-detector-freeze-phase2-real-data` | `51e4278309b7d32917b85903323a63f81d9e9b6a` | Existing Phase 1 freeze branch; preserved |
| `archive/phase1-detector-freeze-v1.0` | `51e4278309b7d32917b85903323a63f81d9e9b6a` | Archive-pointer branch; movable ref |
| `main-phase2` | `51e4278309b7d32917b85903323a63f81d9e9b6a` at creation | Created from the exact Phase 1 baseline; Phase 2 commits are descendants |

## Phase 1 tag and GitHub Release

**Status: created and verified**

- Annotated tag: [`phase1-detector-freeze-v1.0`](https://github.com/uniqueteamyemen/CHAOS/releases/tag/phase1-detector-freeze-v1.0)
- Tag object SHA: `96301238ef79acd7ef39ec91e84ddd945f22b4aa`
- Tag target: `51e4278309b7d32917b85903323a63f81d9e9b6a` — exact canonical Phase 1 commit.
- GitHub Release: https://github.com/uniqueteamyemen/CHAOS/releases/tag/phase1-detector-freeze-v1.0
- The tag is annotated but unsigned (`verification: unsigned`).
- GitHub currently reports the release as `immutable: false`; the tag ref and release are therefore not protected against an administrator moving or deleting them. Do not describe them as cryptographically signed or platform-locked.

The P2.2 workflow creates the tag only if absent, verifies any pre-existing tag points to the exact baseline, creates the release if absent, and attaches:
- `docs/PHASE1_DETECTOR_FREEZE.md`
- `structural_engine/isolated_break_detector_v1/results/real_data_transition_scan.json`
- `structural_engine/isolated_break_detector_v1/results/SHA256SUMS.txt`

The workflow step re-applies these release assets with `gh release upload --clobber` on subsequent runs to keep the release complete.

## Phase 1 integrity

- The Phase 1 freeze branch and archive-pointer branch remain separate from Phase 2 development.
- The frozen detector implementation and historical `experiments/` tree are read-only for this work.
- Phase 2 source code, configuration, tests, and outputs live outside `experiments/`.
- The Phase 1 report, transition scan, and SHA-256 inventory remain the baseline evidence.
- A Git tag is a ref to an immutable Git object, but the tag ref itself can be moved unless a repository tag ruleset protects it.

## Protection status — verified 17 November 2026

The repository now has an active branch ruleset that matches `main-phase2`.

Observed GitHub state:

- Branch endpoint: `protected: true`.
- Ruleset ID: `27488330`, name `main-phase2`, target `branch`, enforcement `active`.
- Ref pattern: `refs/heads/main-phase2`.
- Active rules: `deletion`, `non_fast_forward`, `required_status_checks` (context `stress`, integration ID `15368`), and `update`.
- `strict_required_status_checks_policy: false`.
- `current_user_can_bypass: always`; the ruleset lists repository roles and three integration actors as bypass actors.

This is active platform-level protection for the working branch. It is not a fully non-bypassable lock: the configured owner/admin bypass remains available. The ruleset does not currently require pull requests, human approvals, or branch-up-to-date checks. The branch API's classic protection object still reports `enabled: false`; the protection observed here comes from the repository ruleset, while the branch metadata correctly reports `protected: true`.

### Workflow compatibility

The prior P2.2 workflow pushed generated reports directly to `main-phase2`, which conflicts with the new update/status-check rules because the `stress` job cannot successfully push before that same job has completed. The workflow was changed to:

- Keep generated report, manifest, checksum inventory, and source snapshots in the workflow workspace and run artifact.
- Publish the reproducible outputs as release assets.
- Tag the source commit without pushing generated results to `main-phase2`.

This keeps the protected branch from depending on a direct bot write during its own required check. The updated workflow is being validated by the P2.2.1 run.

### Remaining protection gap

No separate tag-targeted ruleset has been verified for `phase1-detector-freeze-v1.0` or `p2.2-historical-stress-v1.0.0`. The Phase 1 release is still reported as `immutable: false`; do not describe those tags/releases as platform-locked. Add a tag ruleset that blocks deletion and updates for the frozen Phase 1 and published P2.2 tags.

The CI immutability guard at `.github/workflows/experiments-immutable.yml` remains in place. `CODEOWNERS` routes review requests to `@uniqueteamyemen`; it does not itself require a review.
