# AG-CUSUM paired screen on Stage H seeds

- CI run: https://github.com/uniqueteamyemen/CHAOS/actions/runs/43729843319
- Commit tested: \`41a9612e421f2710526076feff43e2cf7cb88f04\`
- Workflow conclusion: success
- Candidate: Gemini Asymmetry-Guarded Bounded CUSUM, defaults unchanged
- Trials: 500 per scenario × 10 scenarios
- Seed base: 1,800,000; exact Stage H generators and seeds
- Artifact SHA-256: \`sha256:3d89a8623c9d74fea7e796b128d090d1952eb1b23171ab50d93a8d97efe7be0c\`

## Aggregate

| Metric | AG-CUSUM |
|---|---:|
| Worst null sequence false-alarm rate | 6.2% |
| Minimum directional sensitivity | 93.0% |
| Mean directional sensitivity | 98.03% |
| Worst pre-onset false-alarm rate | 0.8% |
| Point-rate 5%/75% gate | FAIL |

## Null cases

| Scenario | False sequences | Rate | Wilson 95% |
|---|---:|---:|---:|
| Gaussian AR(1) | 25/500 | 5.0% | 3.41%–7.28% |
| Gaussian AR(1), variance jump | 13/500 | 2.6% | 1.53%–4.40% |
| Student-t3 AR(1) | 31/500 | 6.2% | 4.40%–8.67% |
| Student-t3 AR(1), variance jump | 25/500 | 5.0% | 3.41%–7.28% |

## Shift cases

| Scenario | Pre-onset false rate | Sensitivity | Mean delay |
|---|---:|---:|---:|
| Gaussian AR(1), positive 3σ | 0.4% | 100% | 14.69 |
| Gaussian AR(1), negative 3σ | 0.6% | 100% | 14.75 |
| Student-t3 AR(1), positive 3σ | 0.6% | 100% | 14.42 |
| Student-t3 AR(1), negative 3σ | 0.8% | 100% | 14.29 |
| Student-t3 AR(1), transition positive 3σ | 0.6% | 95.2% | 20.86 |
| Student-t3 AR(1), transition negative 3σ | 0.2% | 93.0% | 20.89 |

## Comparison to Stage H candidates on the same seeds

| Candidate | Worst null false rate | Minimum sensitivity |
|---|---:|---:|
| C default | 97.8% | 100% |
| C h=24 | 44.8% | 99.6% |
| E h=24 | 21.8% | 91.4% |
| F h=16 | 27.8% | 91.2% |
| **AG-CUSUM** | **6.2%** | **93.0%** |

## Interpretation

AG-CUSUM is the strongest candidate in this lab to date. It suppresses the
Student-t3 AR(1) variance-jump null to 5.0% point rate and keeps transition-shift
sensitivity at 93.0% or better. However, Student-t3 AR(1) without a variance jump
produced 31 false-positive sequences (6.2%; Wilson upper 8.67%). It therefore
does not pass the 5% gate and is not approved.

The first-difference scale ratio to marginal scale had median 0.668, while
median estimated rho was 0.542. This is consistent with the stationary AR(1)
relationship \`sd(diff)/sqrt(2) = sigma*sqrt(1-rho)\`: differencing did not
remove serial dependence and reduced the scale estimate under positive rho.

Next step is an untouched-seed confirmation with the exact same parameters;
no tuning will be performed using this paired-screen result.
