import { FLEET_50_SERIES, FleetSeriesItem } from '../src/data/fleet50Series.ts';
import { FLEET_2013_TRANSITION_DATA } from '../src/data/transition2013Data.ts';
import {
  computeFleetCalculus,
  DEFAULT_CALCULUS_PARAMS,
  CalculusParameters,
  SeriesCalculusResult
} from '../src/utils/humanImpactCalculus.ts';
import { evaluateCausalCircuitBreaker } from '../src/utils/causalCircuitBreaker.ts';

// Helper to get normalized stress for any year
function getStressForYear(series: FleetSeriesItem, year: number): number {
  if (year === 2013) {
    const d = FLEET_2013_TRANSITION_DATA[series.id];
    if (d) return d.normalizedStress2013;
  }
  const bm = series.benchmarks.find(b => b.year === year);
  if (bm) return bm.normalizedStress;
  // fallback
  return series.benchmarks[series.benchmarks.length - 1].normalizedStress;
}

// Compute single series score for any year
function computeSeriesScore(series: FleetSeriesItem, year: number, params: CalculusParameters = DEFAULT_CALCULUS_PARAMS): number {
  const rawStress = getStressForYear(series, year);
  const gamma = series.gamma;
  const tau = year === 2008 ? series.snapshot2008.observedDurationYears : series.defaultDurationYears;
  const durationMultiplier = Math.sqrt(Math.max(0.5, tau / 3.0));

  const natureComponent = (1.0 - gamma) * rawStress * params.natureVulnerabilityCoupling;
  const humanComponent = gamma * rawStress * params.humanDecisionCoupling * durationMultiplier;

  const B = Math.pow({
    1973: 1.0,
    1980: 1.25,
    1990: 1.60,
    2001: 2.10,
    2008: 2.75,
    2013: 3.15,
    2020: 3.80,
    2024: 4.10
  }[year] || 2.5, params.bufferingShieldPower);

  const Gamma = 1.0 + (({
    1973: 1.10,
    1980: 1.25,
    1990: 1.35,
    2001: 1.50,
    2008: 1.85,
    2013: 2.10,
    2020: 2.40,
    2024: 2.55
  }[year] || 1.5) - 1.0) * params.reboundCostTax;

  let bufferedImpact: number;
  if (humanComponent + natureComponent >= 0) {
    bufferedImpact = (natureComponent + humanComponent) * Math.min(2.0, Math.sqrt(B));
  } else {
    bufferedImpact = ((natureComponent + humanComponent) / Math.max(0.8, Math.sqrt(B))) * (1.0 + (Gamma - 1.0) * gamma);
  }

  return parseFloat(bufferedImpact.toFixed(3));
}

export interface TransitionMetrics {
  transitionName: string;
  startYear: number;
  endYear: number;
  deltaYears: number;
  hitRate: number; // percentage [0, 100]
  mae: number;
  actualPulse: number;
  predPulse: number;
  pulseError: number;
  actualTurbulence: number;
  predTurbulence: number;
  turbulenceError: number;
}

// 1. Formula Baseline (F1: Pure exponential memory decay)
function predictScoreF1(series: FleetSeriesItem, score0: number, deltaYears: number): number {
  const tau = series.defaultDurationYears;
  const decayFactor = Math.exp(-deltaYears / Math.max(1.0, tau));
  return parseFloat((score0 * decayFactor).toFixed(3));
}

// 2. Improvement 1 (F2: Layered Accumulation + Debt Hysteresis)
function predictScoreF2(series: FleetSeriesItem, score0: number, deltaYears: number): number {
  const tau = series.defaultDurationYears;
  if (series.layer === 'infrastructure') {
    // If infrastructure enablement was positive, it accumulates capital
    if (score0 > 0) {
      return parseFloat((score0 * (1.0 + 0.05 * deltaYears)).toFixed(3));
    } else {
      // Degraded infrastructure decays slowly
      return parseFloat((score0 * Math.exp(-deltaYears / (tau * 1.5))).toFixed(3));
    }
  } else if (series.id === 's38-global-debt-gdp' || series.id === 's36-central-bank-assets' || series.id === 's46-forcibly-displaced') {
    // Hysteresis effect: structural financial liabilities persist
    return parseFloat((score0 * Math.exp(-deltaYears / (tau * 2.5))).toFixed(3));
  } else {
    // Standard exponential decay
    return parseFloat((score0 * Math.exp(-deltaYears / Math.max(1.0, tau))).toFixed(3));
  }
}

// 3. Improvement 2 (F3: Layered Accumulation + Structural Hysteresis + Era Buffer Adaptation)
function predictScoreF3(series: FleetSeriesItem, score0: number, deltaYears: number, startYear: number, endYear: number): number {
  const tau = series.defaultDurationYears;
  const B_start = Math.sqrt({ 1973: 1.0, 1980: 1.25, 1990: 1.60, 2001: 2.10, 2008: 2.75, 2013: 3.15, 2020: 3.80, 2024: 4.10 }[startYear] || 2.5);
  const B_end = Math.sqrt({ 1973: 1.0, 1980: 1.25, 1990: 1.60, 2001: 2.10, 2008: 2.75, 2013: 3.15, 2020: 3.80, 2024: 4.10 }[endYear] || 2.5);
  const eraBufferRatio = B_end / B_start;

  if (series.layer === 'infrastructure') {
    if (score0 > 0) {
      // Capital expansion coupled with technological buffer growth
      return parseFloat((score0 * (1.0 + 0.04 * deltaYears) * Math.min(1.3, eraBufferRatio)).toFixed(3));
    } else {
      return parseFloat((score0 * Math.exp(-deltaYears / (tau * 1.5))).toFixed(3));
    }
  } else if (series.id === 's38-global-debt-gdp' || series.id === 's36-central-bank-assets' || series.id === 's46-forcibly-displaced') {
    // Deep structural hysteresis
    return parseFloat((score0 * Math.exp(-deltaYears / (tau * 2.8))).toFixed(3));
  } else if (series.layer === 'nature') {
    // Cyclical mean-reversion towards 0
    return parseFloat((score0 * Math.exp(-deltaYears / Math.max(1.5, tau * 0.8))).toFixed(3));
  } else {
    // Human decisions
    return parseFloat((score0 * Math.exp(-deltaYears / Math.max(1.0, tau))).toFixed(3));
  }
}

// Function to evaluate transition for a given prediction function
function evaluateTransition(
  startYear: number,
  endYear: number,
  predictFn: (series: FleetSeriesItem, score0: number, deltaYears: number, startYear: number, endYear: number) => number,
  label: string
): TransitionMetrics {
  const deltaYears = endYear - startYear;
  let hits = 0;
  let absErrorSum = 0;
  let actualPulseSum = 0;
  let predPulseSum = 0;
  let actualTurbSum = 0;
  let predTurbSum = 0;

  for (const series of FLEET_50_SERIES) {
    const s0 = computeSeriesScore(series, startYear);
    const s1_actual = computeSeriesScore(series, endYear);
    const s1_pred = predictFn(series, s0, deltaYears, startYear, endYear);

    const deltaActual = s1_actual - s0;
    const deltaPred = s1_pred - s0;

    // Directional Hit Check:
    // If sign matches, or both change by less than threshold (|delta| < 0.04)
    const sameSign = (deltaActual > 0 && deltaPred > 0) || (deltaActual < 0 && deltaPred < 0);
    const bothNegligible = Math.abs(deltaActual) < 0.04 && Math.abs(deltaPred) < 0.04;
    if (sameSign || bothNegligible) {
      hits++;
    }

    absErrorSum += Math.abs(s1_actual - s1_pred);
    actualPulseSum += s1_actual;
    predPulseSum += s1_pred;
    actualTurbSum += Math.abs(s1_actual);
    predTurbSum += Math.abs(s1_pred);
  }

  const n = FLEET_50_SERIES.length;
  const mae = parseFloat((absErrorSum / n).toFixed(3));
  const hitRate = parseFloat(((hits / n) * 100).toFixed(1));
  const actualPulse = parseFloat(actualPulseSum.toFixed(2));
  const predPulse = parseFloat(predPulseSum.toFixed(2));
  const actualTurb = parseFloat(actualTurbSum.toFixed(2));
  const predTurb = parseFloat(predTurbSum.toFixed(2));

  return {
    transitionName: `${startYear} → ${endYear}`,
    startYear,
    endYear,
    deltaYears,
    hitRate,
    mae,
    actualPulse,
    predPulse,
    pulseError: parseFloat(Math.abs(actualPulse - predPulse).toFixed(2)),
    actualTurbulence: actualTurb,
    predTurbulence: predTurb,
    turbulenceError: parseFloat(Math.abs(actualTurb - predTurb).toFixed(2))
  };
}

console.log('=== STEP 1: ANALYSIS OF 2008 FOR THE 50 SERIES ===');
const snap2008 = computeFleetCalculus({ ...DEFAULT_CALCULUS_PARAMS, targetYear: 2008 });
console.log('2008 Net Human Pulse:', snap2008.netHumanPulse);
console.log('2008 Total Turbulence Energy:', snap2008.totalTurbulenceEnergy);
console.log('2008 Layer Shares:', snap2008.layerShares);
console.log('2008 Strain Distribution:', snap2008.strainDistribution);

const topStrains2008 = [...snap2008.items].sort((a, b) => a.finalScore - b.finalScore).slice(0, 5);
console.log('Top 5 Human Strains in 2008:');
topStrains2008.forEach(i => console.log(`  ${i.series.id} (${i.series.nameAr}): score = ${i.finalScore}`));

const topEnablers2008 = [...snap2008.items].sort((a, b) => b.finalScore - a.finalScore).slice(0, 5);
console.log('Top 5 Human Enablers in 2008:');
topEnablers2008.forEach(i => console.log(`  ${i.series.id} (${i.series.nameAr}): score = ${i.finalScore}`));

console.log('\n=== STEP 2 & 3: BASELINE (F1) ON 2008 → 2013 ===');
const f1_2008_2013 = evaluateTransition(2008, 2013, (s, s0, dt) => predictScoreF1(s, s0, dt), 'F1_Baseline');
console.log('F1 on 2008 -> 2013:', f1_2008_2013);

console.log('\n=== STEP 4: BASELINE (F1) ON ALL DEVELOPMENT TRANSITIONS ===');
const devTransitions = [
  [1973, 1980],
  [1980, 1990],
  [1990, 2001],
  [2001, 2008],
  [2008, 2013],
  [2013, 2020]
];

const baselineResults = devTransitions.map(([y0, y1]) =>
  evaluateTransition(y0, y1, (s, s0, dt) => predictScoreF1(s, s0, dt), 'F1_Baseline')
);
console.table(baselineResults);

console.log('\n=== STEP 5: TEST IMPROVEMENT 1 (F2) ACROSS ALL DEVELOPMENT TRANSITIONS ===');
const f2Results = devTransitions.map(([y0, y1]) =>
  evaluateTransition(y0, y1, (s, s0, dt) => predictScoreF2(s, s0, dt), 'F2_Improvement')
);
console.table(f2Results);

console.log('\n=== STEP 5: TEST IMPROVEMENT 2 (F3) ACROSS ALL DEVELOPMENT TRANSITIONS ===');
const f3Results = devTransitions.map(([y0, y1]) =>
  evaluateTransition(y0, y1, (s, s0, dt, yA, yB) => predictScoreF3(s, s0, dt, yA, yB), 'F3_Final')
);
console.table(f3Results);

console.log('\n=== STEP 6: HOLDOUT TEST (2020 → 2024) [STRICTLY EXECUTED ONCE] ===');
const holdoutBaseline = evaluateTransition(2020, 2024, (s, s0, dt) => predictScoreF1(s, s0, dt), 'Holdout_Baseline');
const holdoutImproved = evaluateTransition(2020, 2024, (s, s0, dt, yA, yB) => predictScoreF3(s, s0, dt, yA, yB), 'Holdout_Improved_F3');
console.log('Holdout Baseline (2020 -> 2024):', holdoutBaseline);
console.log('Holdout Improved F3 (2020 -> 2024):', holdoutImproved);

console.log('\n=== COMBINED FINAL COMPARISON TABLE ===');
const allTransitions = [...devTransitions, [2020, 2024]];
const finalTable = allTransitions.map(([y0, y1]) => {
  const b = evaluateTransition(y0, y1, (s, s0, dt) => predictScoreF1(s, s0, dt), 'Baseline');
  const imp = evaluateTransition(y0, y1, (s, s0, dt, yA, yB) => predictScoreF3(s, s0, dt, yA, yB), 'Improved');
  return {
    Transition: `${y0} → ${y1}${y0 === 2020 ? ' (Holdout)' : ''}`,
    'Baseline Hit Rate': `${b.hitRate}%`,
    'Improved Hit Rate': `${imp.hitRate}%`,
    'Baseline MAE': b.mae,
    'Improved MAE': imp.mae,
    'Human Pulse Error (Imp)': imp.pulseError,
    'Turbulence Error (Imp)': imp.turbulenceError
  };
});
console.table(finalTable);
