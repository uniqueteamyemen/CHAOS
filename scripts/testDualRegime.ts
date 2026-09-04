/**
 * Systematic evaluation of Dual-Regime Model (Normal vs Systemic Shock):
 * - If Crisis Regime is false -> pure F3 (clean accumulation & smooth decay)
 * - If Crisis Regime is true (2008 & 2020) -> adjusts capital expansion slowdown and financial strain drag
 */
import { FLEET_50_SERIES, FleetSeriesItem } from '../src/data/fleet50Series.ts';
import { DEFAULT_CALCULUS_PARAMS } from '../src/utils/humanImpactCalculus.ts';

function computeRawImpact(series: FleetSeriesItem, year: number): number {
  const bm = series.benchmarks.find(b => b.year === year);
  const rawStress = bm ? bm.normalizedStress : 0.0;
  const gamma = series.gamma;
  const tau = series.defaultDurationYears;
  const durationMultiplier = Math.sqrt(Math.max(0.5, tau / 3.0));

  const natureComponent = (1.0 - gamma) * rawStress * DEFAULT_CALCULUS_PARAMS.natureVulnerabilityCoupling;
  const humanComponent = gamma * rawStress * DEFAULT_CALCULUS_PARAMS.humanDecisionCoupling * durationMultiplier;

  const B = 2.0;
  const Gamma = 2.0;

  if (humanComponent + natureComponent >= 0) {
    return (natureComponent + humanComponent) * Math.min(2.0, Math.sqrt(B));
  } else {
    return ((natureComponent + humanComponent) / Math.max(0.8, Math.sqrt(B))) * (1.0 + (Gamma - 1.0) * gamma);
  }
}

function isCrisisRegime(year: number): boolean {
  const s40 = FLEET_50_SERIES.find(s => s.id === 's40-policy-uncertainty')?.benchmarks.find(b => b.year === year)?.normalizedStress || 0;
  const s34 = FLEET_50_SERIES.find(s => s.id === 's34-us-10y-treasury')?.benchmarks.find(b => b.year === year)?.normalizedStress || 0;
  const s38 = FLEET_50_SERIES.find(s => s.id === 's38-global-debt-gdp')?.benchmarks.find(b => b.year === year)?.normalizedStress || 0;

  const score = -s40 * 0.4 - s34 * 0.3 - s38 * 0.3;
  return score > 0.52;
}

const transitions = [
  { from: 1973, to: 1980 },
  { from: 1980, to: 1990 },
  { from: 1990, to: 2001 },
  { from: 2001, to: 2008 },
  { from: 2008, to: 2013 },
  { from: 2013, to: 2020 },
  { from: 2020, to: 2024 }
];

console.log('=== SYSTEMATIC TRANSITION EVALUATION (DUAL REGIME: NORMAL VS CRISIS) ===');

const results = transitions.map(t => {
  const deltaYears = t.to - t.from;
  const crisis = isCrisisRegime(t.from);

  let hitCountF3 = 0;
  let hitCountDual = 0;
  let maeF3 = 0;
  let maeDual = 0;

  for (const s of FLEET_50_SERIES) {
    const s0 = computeRawImpact(s, t.from);
    const s1 = computeRawImpact(s, t.to);
    const tau = s.defaultDurationYears;
    const actualDelta = s1 - s0;

    // F3 Baseline:
    let s1F3 = s0;
    if (s.layer === 'infrastructure') {
      s1F3 = s0 > 0 ? s0 * (1 + 0.04 * deltaYears) : s0 * Math.exp(-deltaYears / (tau * 1.5));
    } else if (s.id === 's38-global-debt-gdp' || s.id === 's36-central-bank-assets' || s.id === 's46-forcibly-displaced') {
      s1F3 = s0 * Math.exp(-deltaYears / (tau * 2.8));
    } else if (s.layer === 'nature') {
      s1F3 = s0 * Math.exp(-deltaYears / Math.max(1.5, tau * 0.85));
    } else {
      s1F3 = s0 * Math.exp(-deltaYears / Math.max(1.0, tau));
    }

    // Dual Regime Model:
    let s1Dual = s0;
    if (!crisis) {
      // Exactly F3 for calm/normal periods (Preserves 76%, 76%, 70%, 56%):
      s1Dual = s1F3;
    } else {
      // In crisis periods (2008 & 2020):
      // 1. Capital accumulation slows down
      // 2. Debt/monetary accommodation stretches
      if (s.layer === 'infrastructure') {
        s1Dual = s0 > 0 ? s0 * (1 + 0.015 * deltaYears) : s0 * Math.exp(-deltaYears / (tau * 1.5));
      } else if (s.id === 's38-global-debt-gdp' || s.id === 's36-central-bank-assets' || s.id === 's46-forcibly-displaced') {
        s1Dual = s0 * Math.exp(-deltaYears / (tau * 3.5)); // prolonged liquidity lock
      } else if (s.layer === 'nature') {
        s1Dual = s0 * Math.exp(-deltaYears / Math.max(1.5, tau * 0.85));
      } else {
        s1Dual = s0 * Math.exp(-deltaYears / Math.max(0.8, tau * 0.8)); // faster short-term policy shock reaction
      }
    }

    const deltaF3 = s1F3 - s0;
    const deltaDual = s1Dual - s0;

    if ((actualDelta >= 0 && deltaF3 >= 0) || (actualDelta < 0 && deltaF3 < 0)) hitCountF3++;
    if ((actualDelta >= 0 && deltaDual >= 0) || (actualDelta < 0 && deltaDual < 0)) hitCountDual++;

    maeF3 += Math.abs(s1 - s1F3);
    maeDual += Math.abs(s1 - s1Dual);
  }

  return {
    Transition: `${t.from} -> ${t.to}`,
    'Regime Type': crisis ? '🚨 CRISIS / PANIC' : '⚖️ STABLE / GROWTH',
    'F3 Hit Rate': `${((hitCountF3 / 50) * 100).toFixed(1)}%`,
    'Dual Hit Rate': `${((hitCountDual / 50) * 100).toFixed(1)}%`,
    'F3 MAE': (maeF3 / 50).toFixed(3),
    'Dual MAE': (maeDual / 50).toFixed(3),
    'Outcome': hitCountDual >= hitCountF3 ? '✅ PRESERVED / IMPROVED' : '⚠️ REGRESSION'
  };
});

console.table(results);
