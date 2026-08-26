---
name: economic-geopolitical-analysis
description: Evidence-led economic and geopolitical pattern analysis for multi-source historical research. Use when defining domain states, comparing institutions and collective actors, linking economic, political, conflict, energy, trade, environmental, or demographic signals, or evaluating lead-lag pathways without causal overclaiming.
---

# Economic–Geopolitical Analysis

## Operating principle

Treat the system as interacting institutions, incentives, constraints, shocks, and collective behaviors. Distinguish observations, measurements, interpretations, and hypotheses. Never treat a country, leader, party, headline, or model weight as a causal variable by default.

## Required workflow

1. Define the unit of analysis, entity set, native frequency, observation date, outcome, and forecast horizon before inspecting results.
2. Build an evidence card for every domain variable: source, version, definition, unit, method, coverage, revisions, missingness, and known breaks.
3. Separate four layers: structural baseline, current regime, triggering event, and outcome. Keep hidden or unmeasured factors as explicit uncertainty references rather than invented variables.
4. Extract domain states from observations available at or before time `t`. Record state probability, rule/model, support, uncertainty, and failure cases.
5. Link states only through explicit temporal edges. Record lag units, lead direction, mediator candidates, confounders, and whether the edge is descriptive, predictive, or causal.
6. Test every cross-domain edge against target-history, prevalence, persistence, and time-shift/block nulls. Apply max-statistic correction when multiple families, thresholds, paths, or horizons were searched.
7. Compare institutions and collective actors through mechanisms and constraints, not labels. Separate policy continuity from leader-specific deviation and measurement noise.
8. Preserve contradictions. A failed edge is evidence for the registry, not a reason to silently remove a domain.

## CHAOS output contract

Emit a `DomainState` and `TransitionEvidence` record containing:

```text
domain, entity, timestamp, native_frequency,
regime_label, regime_probability, source_observations,
lead_profile, uncertainty, failure_cases,
edge_status, null_method, evidence_refs
```

Allowed edge statuses are `candidate`, `supported_predictive`, `unresolved`, `rejected`, and `not_testable`. The words causal, mechanism, driver, and cause require an independently justified causal design; predictive importance or attention is insufficient.

## Do not do

Do not average conflicting sources without a contract. Do not annualize daily or event-native data merely to join an annual panel. Do not infer geopolitical intent from news volume. Do not use future outcomes to define present states, thresholds, entity groups, or labels. Do not promote a pattern because it is narratively plausible.

## Escalation

When a cross-domain result is promising, freeze the path and test it on a new source, entity holdout, time window, and appropriate null before adding another node. When a result fails, test whether the failure is due to outcome definition, coverage, lag, or genuine absence; do not retune until the new contract is recorded.
