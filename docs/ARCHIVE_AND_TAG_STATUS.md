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

The CI immutability guard remains at `.github/workflows/experiments-immutable.yml`. It checks the frozen `experiments/**` tree on pull requests and direct pushes to `main-phase2`.

A repository ruleset is now visible:

- Ruleset ID: `27488330`
- Name: `main-phase2`
- Enforcement: `active`
- Rules: `deletion`, `non_fast_forward`
- Ref condition: `include: []`, `exclude: []`

**This is not verified as effective protection for `main-phase2`.** GitHub's ruleset condition requires at least one included ref pattern to match; the current empty include list does not explicitly select `refs/heads/main-phase2`. The branch API also reports `protected: false`. Even if the ref condition is corrected, the current ruleset has no pull-request requirement and no required status checks. It therefore does not provide the intended PR/CI gate.

The connected GitHub integration cannot read the classic branch-protection endpoint (HTTP 403) and exposes no ruleset create/update action. GitHub's repository-ruleset create/update endpoint requires repository **Administration: write** permission. Consequently, platform-level activation could not be completed through the currently connected integration. Do not describe the branch as protected.

There is also an automation dependency to resolve before requiring PRs: `.github/workflows/real-data-stress.yml` currently commits generated reports and manifests directly to `main-phase2` using `GITHUB_TOKEN`. A PR-only rule would block that write. Move generated outputs to a dedicated results branch/PR or keep them as release artifacts before enforcing a PR-only rule.

Recommended configuration, after the workflow is adjusted:

1. Branch ruleset target `branch`, condition `include: ["refs/heads/main-phase2"]`, enforcement `active`.
2. Rules: prevent deletion, prevent non-fast-forward updates, require pull requests, and require the verified CI contexts for `experiments-immutable` and the P2.2 contract-test workflow.
3. Do not require a human approval from the sole owner account as the only approver; this can make owner-authored PRs unmergeable. Keep CODEOWNERS as review routing unless a distinct reviewer is added.
4. Add a separate tag ruleset for `phase1-detector-freeze-v1.0` and the P2.2 release tag to prevent tag deletion or movement.

The current ruleset is recorded for traceability, but its present target condition and limited rule set are insufficient. The existing CODEOWNERS file routes requests to `@uniqueteamyemen`; it does not enforce approval by itself.
