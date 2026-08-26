# CHAOS

**CHAOS** is the independent workspace for the governed historical-data layer, readiness gates, experimental contracts, and structural-analysis prototypes that were previously developed under the working name `market-intelligence-engine`.

> The original `market-intelligence-engine` repository is not copied as an implementation target and is not modified by this project. CHAOS is an independent research and data-readiness repository.

## Current scope

The repository preserves the catalog-first acquisition work, variable-level coverage matrices, raw-panel extraction specifications, gap analyses, provenance notes, and the draft experimental contract for `macro_plus_eia_energy` covering 2000–2024 at annual frequency.

The current baseline contract is **review-only**. It does not authorize TFT training, structure learning, surrogate testing, model deployment, or architecture changes. The selected raw annual matrix uses eleven source-separated variables from World Bank WDI, IMF WEO, and EIA. Daily, monthly, and event-driven assets remain separate layers.

## Repository layout

| Directory | Purpose |
|---|---|
| `docs/` | Project reports, acquisition notes, governance and retention documentation. |
| `catalog_first/` | Catalog-first inventories, readiness reports, coverage summaries, selected derived panels and tools. |
| `experimental_contracts/` | Pre-training contracts and machine-readable dataset configurations. |
| `structural_engine/` | Independent Python/TypeScript prototype for governed structural analysis; it does not modify the original product. |
| `campaign/` | Earlier acquisition campaign outputs and quality exceptions. |
| `tooling/` | Reproducible local scripts used to build inventories, panels, profiles and reports. |
| `data/derived/` | Small, reproducible derived extracts that are safe to version. |
| `data/visuals/` | Deterministic charts and visual readiness summaries. |
| `manifests/` | File inventories, checksums, excluded-large-asset records and provenance maps. |

## Large and licensed source assets

The complete bulk archives and some large staged files are intentionally not committed to GitHub. They remain in the local workspace with their original paths, checksums, source versions, and license notes recorded in `manifests/`. This avoids violating GitHub size limits, avoids duplicating licensed third-party distributions without a terms review, and keeps the repository usable. The repository contains the code and manifests needed to reproduce or reconnect those assets locally.

## Scientific guardrails

CHAOS preserves raw observations and source conflicts. It does not force source reconciliation, blanket imputation, universal transformations, or frequency mixing. Temporal precedence is not treated as causality. Rejected patterns must remain auditable. Any future model or experiment requires an explicit reviewed contract before execution.

## Status

The repository is private and is being populated from the independent workspace. The initial commit will contain the documented project layer, contracts, code, reports, compact derived artifacts, and manifests. Large raw/staged datasets remain external to Git until their storage, licensing, and access policy are separately approved.
