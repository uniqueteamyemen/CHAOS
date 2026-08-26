# Autonomous Structural Learning Campaign

This workspace contains an isolated implementation of the historical acquisition, coverage, provenance, transformation, surrogate-validation, pattern-registry, and TypeScript compatibility layers described in the master directive.

## Governing boundary

The workspace does not modify `market-intelligence-engine`. It does not create mock observations, fill raw gaps, force source reconciliation, or treat a candidate edge as proof of physical causality.

## Current contents

| Path | Role |
|---|---|
| `config/execution_policy.json` | Non-negotiable data and inference policies |
| `raw_ingest.py` | Exact response-byte persistence with SHA-256 and provenance |
| `coverage_model.py` | Variable-level coverage and unresolved source-conflict records |
| `transformations.py` | Explicit derived transformations such as CPI real-value conversion and observed z-scores |
| `surrogates.py` | Circular-shift and block-permutation null testing |
| `discovery.py` | Optional Tigramite PCMCI discovery on real observed matrices |
| `pattern_registry.py` | Append-only candidate/rejected/golden pattern records |
| `CausalSignalAdapter.ts` | Generic scientific payload adapter with compatibility mapping kept separate |
| `campaign/` | Raw captures, coverage matrix, manifests, and quality exceptions from bounded acquisition |
| `tests/` | Reproducible unit tests for the safety boundaries and core data structures |

## What is intentionally not claimed

The bounded acquisition currently proves the mechanics with real payloads and records source access exceptions. It is not a completed 25-year bulk extract for every source. Restricted sources and very large archives require authorized credentials, scoped queries, and source-specific extraction plans. No value is inferred where access failed.

## Execution checks

```bash
PYTHONPATH=. pytest -q tests/test_core.py
./node_modules/.bin/tsc --noEmit
```

Discovery must receive a real, observed matrix. The module intentionally does not generate fallback or synthetic data when Tigramite is unavailable.
