---
name: chaos-system-architecture-review
description: End-to-end architecture review for CHAOS and governed analytical pipelines. Use when designing or auditing source adapters, historical replay, domain-state extraction, transition graphs, path composition, provenance, registry promotion, or runtime compatibility boundaries.
---

# CHAOS System Architecture Review

## Architecture boundary

Keep CHAOS as an independent research and evidence system. Do not modify `market-intelligence-engine` while designing or testing historical patterns. Keep scientific payloads separate from runtime-compatible signals; promotion is a later, explicit decision.

## Pipeline review order

Review every proposal in this order:

```text
Raw bytes → Source manifest → Coverage gate → Contract
→ Domain adapter → Domain state → Transition evidence
→ Null/OOS/stability → Pattern registry → Compatibility adapter
```

For each boundary, name inputs, outputs, version, owner, failure behavior, and immutable evidence references. Reject undocumented implicit conversions.

## Non-negotiable checks

1. Raw files are immutable and hashed. Derived staging is separate and reproducible.
2. Source adapters preserve native definitions, units, frequencies, revisions, and conflicts.
3. Daily, event-native, monthly, and annual data are not silently aggregated or broadcast across frequency.
4. Future observations cannot influence thresholds, labels, entity groups, model selection, or emitted triggers.
5. Every experiment has a frozen contract, chronological splits, explicit baselines, and a saved run manifest.
6. Multiple paths, thresholds, outcomes, horizons, or proxies require max-statistic or equivalent search correction.
7. Pattern records include supported, rejected, unresolved, not-testable, and failure evidence; absence of evidence is not a positive edge.
8. Causal classification is never inferred from attention, feature importance, predictive gain, or a transition score alone.
9. Runtime compatibility must preserve the scientific payload, uncertainty, evidence refs, failure cases, and source conflicts.
10. A failed source or unavailable credential is recorded; no placeholder or synthetic observation is substituted.

## Domain-state interface

Use a stable neutral record:

```text
DomainState {
  domain, entity, timestamp, native_frequency,
  regime_label, regime_probability, source_observations,
  lead_profile, uncertainty, failure_cases
}
```

Use a separate edge record:

```text
TransitionEvidence {
  source_state, target_state, lag,
  split, metric, null_method, p_value,
  entity_holdout, source_refs, edge_status
}
```

The transition layer may combine states probabilistically, but must not rewrite a descriptive edge as a causal edge.

## Composition review

Prefer a hierarchical state-space or dynamic Bayesian network with domain-specific adapters over a monolithic model when domains differ in frequency, missingness, or measurement. Compose paths through explicit transition probabilities and interactions. Compare every composed path with single-domain and target-history baselines. Keep the graph sparse and prune only through recorded evidence, never narrative preference.

## Promotion gate

A pattern may move from research registry toward runtime compatibility only after a frozen external replication or independent domain test, adequate null controls, time and entity stability, documented coverage, explicit uncertainty, and a review decision. The adapter must not erase the distinction between `scientificClassification` and `runtimeCompatibility`.

## Review deliverable

Return an architecture map, contract mismatches, data-frequency risks, leakage risks, provenance gaps, failure cases, promotion status, and the smallest safe next change. Do not recommend rewriting the host product when an isolated adapter or research-layer change is sufficient.
