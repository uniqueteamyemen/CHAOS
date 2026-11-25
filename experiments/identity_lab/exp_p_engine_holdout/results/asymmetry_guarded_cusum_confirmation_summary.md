# AG-CUSUM untouched-seed confirmation

- Workflow: https://github.com/uniqueteamyemen/CHAOS/actions/runs/43730087993
- Commit tested: \`536953c1691f6b9b007408a3293123b919deb2d5\`
- Workflow conclusion: success
- 1,000 trials × 10 scenarios = 10,000 independent synthetic series
- Seed base: \`7,300,000\`, disjoint from Stage H and Stage K screen
- Parameters: unchanged Gemini defaults (psi=1.8, gamma=0.90, k=0.50, h=9.5, dwell=4, asymmetry=3.5, cooldown=6)

## Aggregate

| Metric | Result |
|---|---:|
| Worst null false-alarm rate | 6.0% |
| Worst null Wilson upper 95% | 7.65% |
| Minimum directional sensitivity | 95.8% |
| Minimum sensitivity Wilson lower 95% | 94.37% |
| Worst pre-onset false-alarm rate | 1.0% |
| Point gate (null <=5%, sensitivity >=75%) | FAIL |
| Confidence gate | FAIL |

## Null scenarios

| Scenario | False sequences | Rate | Wilson 95% |
|---|---:|---:|---:|
| Gaussian AR(1) | 43/1000 | 4.3% | 3.21%–5.74% |
| Gaussian AR(1), variance jump | 34/1000 | 3.4% | 2.44%–4.71% |
| Student-t3 AR(1) | 60/1000 | 6.0% | 4.69%–7.65% |
| Student-t3 AR(1), variance jump | 58/1000 | 5.8% | 4.51%–7.42% |

## Shift scenarios

| Scenario | Pre-onset false rate | Sensitivity | Mean delay |
|---|---:|---:|---:|
| Gaussian AR(1), positive 3σ | 0.3% | 100% | 14.85 |
| Gaussian AR(1), negative 3σ | 0.2% | 100% | 14.84 |
| Student-t3 AR(1), positive 3σ | 0.8% | 100% | 14.28 |
| Student-t3 AR(1), negative 3σ | 0.3% | 100% | 14.37 |
| Student-t3 AR(1), transition positive 3σ | 0.6% | 96.3% | 21.15 |
| Student-t3 AR(1), transition negative 3σ | 1.0% | 95.8% | 21.22 |

## Decision

The AG-CUSUM result is repeatable on fresh seeds and markedly improves on
C/E/F in the Stage H paired screen. It suppresses the variance-jump Student-t3
null to 5.8% and preserves at least 95.8% sensitivity. However, the two
Student-t3 null conditions remain above the 5% point threshold, and their
Wilson upper bounds remain above 7%.

**Decision: preserve as the strongest current experimental challenger; do not
promote or merge into the production P-engine.** No parameter was tuned using
the confirmation set.
