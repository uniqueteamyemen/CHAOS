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

## Protection status

The CI immutability guard is maintained at `.github/workflows/experiments-immutable.yml`. It detects changes to `experiments/**` on pull requests and direct pushes to `main-phase2`; the workflow has passed once for the phase2 setup commit.

The connected GitHub integration returned HTTP 403 for branch-protection reads and does not expose a branch-protection/ruleset mutation action. Therefore:
- The CI guard exists and runs, but a GitHub ruleset requiring that check has **not** been enabled or verified.
- No GitHub tag ruleset protecting Phase 1 or P2.2 tags has been enabled or verified.
- CODEOWNERS routes review requests to `@uniqueteamyemen`, but does not itself enforce approval.

For platform-level protection, configure GitHub repository rulesets for `main-phase2` and the release tags: require the `experiments-immutable` check, block force-push and deletion, and require owner review for protected files and paths.
