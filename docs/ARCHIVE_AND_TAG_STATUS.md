# Phase 1 Archive and Tag Status

**Verification date:** 17 November 2026  
**Canonical Phase 1 commit:** `51e4278309b7d32917b85903323a63f81d9e9b6a`

## Verified references

| Reference | Target | Status |
|---|---|---|
| `phase1-detector-freeze-phase2-real-data` | `51e4278309b7d32917b85903323a63f81d9e9b6a` | Existing Phase 1 freeze branch; preserved |
| `main-phase2` | `51e4278309b7d32917b85903323a63f81d9e9b6a` at creation | Created from the exact Phase 1 freeze commit; Phase 2 changes are committed only after this baseline |
| `archive/phase1-detector-freeze-v1.0` | `51e4278309b7d32917b85903323a63f81d9e9b6a` | Additional archive-pointer branch created |

The archive-pointer branch is a branch, not an annotated or signed Git tag. Branch references can move and must not be described as immutable tags.

## Git tags and GitHub Releases

At verification, the GitHub tags query returned no tags and the Releases endpoint returned an empty list. The connected GitHub toolset available in this execution exposes file/branch operations but does not expose creation of annotated Git tag objects, tag references, or GitHub Releases. Therefore, no tag or release is claimed as created.

To complete the Git tag step from a Git client with push access:

```bash
git fetch origin
git tag -a phase1-detector-freeze-v1.0 51e4278309b7d32917b85903323a63f81d9e9b6a -m "CHAOS Phase 1 detector freeze v1.0"
git push origin refs/tags/phase1-detector-freeze-v1.0
```

Then publish a GitHub Release targeting that tag and attach the Phase 1 freeze report, original real-data transition scan, and SHA-256 inventory. The release must target the canonical freeze commit, not the later Phase 2 branch head.

## Phase 1 integrity

- Phase 1 branch and archive-pointer branch remain separate from Phase 2 development.
- The frozen detector implementation and historical `experiments/` tree are read-only for this work.
- Phase 2 source code, configuration, tests, and outputs live outside `experiments/`.
- The Phase 1 report and SHA-256 inventory remain the baseline evidence.

## Protection status

The CI immutability guard is maintained at `.github/workflows/experiments-immutable.yml`. It detects changes to `experiments/**` on pull requests and direct pushes to `main-phase2`.

The connected GitHub integration returned HTTP 403 for branch-protection reads and does not expose a branch-protection/ruleset mutation action. Therefore, the guard workflow is present, but a GitHub ruleset that blocks merges when the guard fails has **not** been enabled or verified. Enable repository ruleset protection in GitHub settings for `main-phase2`, require the immutability check, disable force-push/deletion for archive references, and require owner approval for protected paths.