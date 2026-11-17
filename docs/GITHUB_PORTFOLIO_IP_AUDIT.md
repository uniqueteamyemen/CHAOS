# GitHub Portfolio — Ownership and License Audit

**Audit date:** 17 November 2026  
**Account:** `uniqueteamyemen`  
**Declared rights holder:** `uniqueteamyemen`  
**Scope:** All 23 repositories returned by the authenticated GitHub account listing.

## 1. Rights-holder declaration

The account owner declares that they are the sole individual owner of the `uniqueteamyemen` GitHub account and the sole owner of the original intellectual-property contributions made in the 23 repositories listed below. The owner further declares that no human co-owner, partner, or independent third-party human rights holder has an ownership interest in those original contributions.

Git author strings such as `manus-ai`, `CHAOS Identity Lab`, and `github-actions[bot]` are declared by the owner to identify AI tools, automated workflows, or test environments that acted under the owner's direction. Those strings are provenance metadata; they are not treated here as independent human ownership claims.

This record documents the owner's declaration and the inspected repository state. It is not a judicial determination, a patent or trademark registration, or a substitute for a written assignment where applicable law requires one.

## 2. Repository inventory and root license status

The following inventory was collected from the GitHub account's repository list and a root-path check for `LICENSE` and `COPYRIGHT_AND_IP_NOTICE.md`. “Absent” means no file was returned at that exact root path on the default branch; it does not prove that no notices exist in subdirectories or elsewhere.

| # | Repository | Visibility | Default branch | Root LICENSE found | Root COPYRIGHT notice found |
|---:|---|---|---|---|---|
| 1 | [Hossam-](https://github.com/uniqueteamyemen/Hossam-) | Public | main | Absent | Absent |
| 2 | [HC-CXL-Sovereign](https://github.com/uniqueteamyemen/HC-CXL-Sovereign) | Public | main | Absent | Absent |
| 3 | [paylock-core](https://github.com/uniqueteamyemen/paylock-core) | Public | main | Absent | Absent |
| 4 | [yaqeen-platform](https://github.com/uniqueteamyemen/yaqeen-platform) | Public | main | Absent | Absent |
| 5 | [adapter-dictionary](https://github.com/uniqueteamyemen/adapter-dictionary) | Public | main | Absent | Absent |
| 6 | [Yemen-Drug](https://github.com/uniqueteamyemen/Yemen-Drug) | Public | main | Absent | Absent |
| 7 | [yemen-pharma-intelligence](https://github.com/uniqueteamyemen/yemen-pharma-intelligence) | Public | main | Absent | Absent |
| 8 | [market-intelligence-engine](https://github.com/uniqueteamyemen/market-intelligence-engine) | Public | master | Absent | Absent |
| 9 | [ssdd-research](https://github.com/uniqueteamyemen/ssdd-research) | Public | main | Present — “All rights reserved”, Copyright Deterministic Solutions & Design | Absent |
| 10 | [deterministic-solutions-design-website](https://github.com/uniqueteamyemen/deterministic-solutions-design-website) | Public | main | Absent | Absent |
| 11 | [paylock-live-evidence](https://github.com/uniqueteamyemen/paylock-live-evidence) | Public | main | Absent | Absent |
| 12 | [pharmayemen-presentation-edition](https://github.com/uniqueteamyemen/pharmayemen-presentation-edition) | Public | main | Absent | Absent |
| 13 | [ssdd-blinded-review](https://github.com/uniqueteamyemen/ssdd-blinded-review) | Public | main | Absent | Absent |
| 14 | [CHAOS](https://github.com/uniqueteamyemen/CHAOS) | Public | main | Present — Proprietary, All Rights Reserved, uniqueteamyemen | Present |
| 15 | [CHAOS-GOV](https://github.com/uniqueteamyemen/CHAOS-GOV) | Private | main | Present — Apache License 2.0 | Absent |
| 16 | [phone-and-tablet-pharma-yemen](https://github.com/uniqueteamyemen/phone-and-tablet-pharma-yemen) | Public | main | Present — MIT License, © 2026 uniqueteamyemen | Absent |
| 17 | [Phone-tablet-pharma-](https://github.com/uniqueteamyemen/Phone-tablet-pharma-) | Public | main | Absent | Absent |
| 18 | [Phone-tablet-pharma-1](https://github.com/uniqueteamyemen/Phone-tablet-pharma-1) | Public | main | Absent | Absent |
| 19 | [traveler-reconstruction](https://github.com/uniqueteamyemen/traveler-reconstruction) | Public | main | Absent | Absent |
| 20 | [traveler-](https://github.com/uniqueteamyemen/traveler-) | Public | main | Absent | Absent |
| 21 | [deterministic-solutions-design-website-last](https://github.com/uniqueteamyemen/deterministic-solutions-design-website-last) | Public | main | Absent | Absent |
| 22 | [CHAOS1](https://github.com/uniqueteamyemen/CHAOS1) | Public | main | Absent | Absent |
| 23 | [CHAOS2](https://github.com/uniqueteamyemen/CHAOS2) | Private | main | Absent | Absent |

## 3. License exceptions that must remain explicit

Three repositories have root license terms other than the proprietary notice now established in CHAOS:

- `CHAOS-GOV` currently has Apache License 2.0.
- `phone-and-tablet-pharma-yemen` currently has the MIT License.
- `ssdd-research` has an All Rights Reserved notice naming Deterministic Solutions & Design.

These files were not overwritten during this audit. The owner may own the original contributions and still have granted permissions under a published license. Replacing a license file on the current branch does not retroactively cancel permissions already granted to recipients of earlier versions. Any future license transition must identify its effective commit/version and preserve a record of prior grants.

The `market-intelligence-engine` repository has no root LICENSE file. Its `package.json` sets `private: true`; that package setting is distinct from the GitHub repository's visibility, which is Public.

## 4. Ownership versus third-party materials

The owner's declaration covers original contributions, subject to applicable law. It does not transfer ownership of:

- Third-party libraries, source code, templates, or AI-provider outputs whose terms govern their use.
- World Bank, USGS, or other source datasets and official publications.
- Third-party logos, icons, images, fonts, trademarks, or embedded media.
- Code or content whose authorship or license cannot be established from repository evidence.

Each repository should maintain source-level notices for those materials. A proprietary root LICENSE must not purport to override a third-party license.

## 5. State of the current CHAOS rights notice

CHAOS now contains:

- `LICENSE` — Proprietary — All Rights Reserved in favor of `uniqueteamyemen`.
- `COPYRIGHT_AND_IP_NOTICE.md` — owner's sole-rights-holder declaration, AI/automation identity explanation, reserved commercial rights, provenance expectations, and third-party rights boundary.
- `THIRD_PARTY_NOTICES.md` and `DATA_SOURCES.md` — source attribution and external-license controls.

The same ownership declaration is reflected in the account-level inventory above. The other repositories have not been mass-relicensed by this change; their existing root license conditions and absent notices are shown transparently in the inventory.

## 6. Recommended repository governance

1. Keep a root copyright/ownership notice in each repository, identifying the rights holder and documenting automated/AI commit identities as execution provenance.
2. Add a proprietary LICENSE only to repositories whose current and historical license strategy is confirmed as proprietary; do not silently replace MIT or Apache grants.
3. Keep a third-party inventory for data, code, templates, media, and dependencies.
4. Use annotated release tags and SHA-256 inventories for important versions. Protect release tags and default branches with repository rulesets; an ordinary annotated tag is not platform-immutable unless the ruleset or GitHub immutable-release setting enforces that.
5. Preserve author, committer, commit, tool, and workflow provenance. Do not rewrite Git history merely to remove AI or automation identities.

**Owner declaration recorded on 17 November 2026: `uniqueteamyemen` — sole individual owner of the account and sole owner of original contributions, as declared by the account owner.**
