# CHAOS Repository Protection Audit

**Audit date:** 17 November 2026  
**Repository:** `uniqueteamyemen/CHAOS`  
**Branch reviewed:** `main-phase2`  
**Branch head at inspection:** `49f3030be6fa4610b2413ccd5700f9b0ec68848f`

## Observed GitHub state

The branch metadata endpoint returned:

- `protected: false`
- branch head `49f3030be6fa4610b2413ccd5700f9b0ec68848f`

The repository ruleset collection returned one active ruleset:

| Field | Observed value |
|---|---|
| Ruleset ID | `27488330` |
| Name | `main-phase2` |
| Target | `branch` |
| Enforcement | `active` |
| Ref include | `[]` |
| Ref exclude | `[]` |
| Rules | `deletion`, `non_fast_forward` |
| Bypass actors | none |

An active ruleset label does not prove that a particular branch is selected. GitHub's ruleset documentation states that one of the `ref_name.include` patterns must match for the condition to pass, and supports explicit patterns such as `refs/heads/main-phase2`, `~DEFAULT_BRANCH`, or `~ALL`. The observed empty `include` does not explicitly target `main-phase2`. Treat the current ruleset as ineffective for the working branch until the include condition is corrected and the effective rules are verified.

Even if the ref condition were corrected, the listed rules only prevent deletion and non-fast-forward updates. They do not require pull requests or status checks. Ordinary fast-forward pushes remain possible under those two rules.

## Integration limitation

The connected GitHub integration returned HTTP 403 for the classic branch-protection read endpoint. Its available `fetch` action is read-only, and no ruleset create/update action is exposed in the current tool connection. GitHub documents that creating or updating a repository ruleset requires repository **Administration: write** permission.

Therefore this audit did not change GitHub repository settings, and platform-level branch protection must not be reported as enabled. The owner can apply the settings through GitHub's repository Settings UI or reconnect an integration with the required Administration: write scope.

## Workflow compatibility issue

Before enforcing a pull-request requirement, refactor `.github/workflows/real-data-stress.yml`. Its current successful-run path commits generated report and manifest files and executes:

```bash
git push origin HEAD:main-phase2
```

A PR-only ruleset would reject that direct bot push. Move generated results to a dedicated results branch and open a PR, or keep generated outputs in versioned release assets without writing them directly to `main-phase2`.

The current `.github/CODEOWNERS` routes files to `@uniqueteamyemen`. Because the account owner is the sole owner, do not require a separate human approval from the same PR author; such a rule can make owner-authored changes unmergeable.

## Recommended ruleset design

After the workflow change and after the CI check contexts have been observed on a test PR:

1. Create an active branch ruleset with `ref_name.include = ["refs/heads/main-phase2"]`.
2. Prevent branch deletion and non-fast-forward updates.
3. Require pull requests for updates to `main-phase2`.
4. Require the successful `experiments-immutable` check and a dedicated P2.2 contract-test check.
5. Keep owner bypass disabled unless a documented emergency path is required.
6. Add a separate tag-targeted ruleset for `phase1-detector-freeze-v1.0` and `p2.2-historical-stress-v1.0.0`, preventing their deletion or movement.

Do not enable a required-check rule until the exact check names are present on a real PR. Do not turn on PR-only enforcement until the direct-push workflow has been redesigned.

## Evidence links

- [GitHub branch metadata](https://github.com/uniqueteamyemen/CHAOS/tree/main-phase2)
- [Current ruleset](https://github.com/uniqueteamyemen/CHAOS/rules/27488330)
- [CODEOWNERS](../.github/CODEOWNERS)
- [P2.2 workflow](../.github/workflows/real-data-stress.yml)
- [GitHub REST API ruleset documentation](https://docs.github.com/en/rest/repos/rules)
