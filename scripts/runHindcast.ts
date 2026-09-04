/**
 * Historical Hindcasting / Backtesting Execution Script
 * Evaluates the Future Forecast Engine logic retrospectively:
 * - Train/Base at t0 -> Project to t1 -> Compare against empirical truth at t1
 * - Transitions tested:
 *   1. 1973 -> 1980
 *   2. 1980 -> 1990
 *   3. 1990 -> 2001
 *   4. 2001 -> 2008
 *   5. 2008 -> 2013
 *   6. 2013 -> 2020
 *   7. 2020 -> 2024 (Holdout Hindcast)
 */

import { FLEET_50_SERIES, FleetSeriesItem } from '../src/data/fleet50Series.ts';
import { DEFAULT_CALCULUS_PARAMS } from '../src/utils/humanImpactCalculus.ts';

function computeScoreAtYear(series: FleetSeriesItem, year: number): number {
  const bm = series.benchmarks.find(b => b.year === year);
  const rawStress = bm ? bm.normalizedStress : 0.0;
  const gamma = series.gamma;
  const tau = series.defaultDurationYears;
  const durationMultiplier = Math.sqrt(Math.max(0.5, tau / 3.0));

  const natureComponent = (1.0 - gamma) * rawStress * DEFAULT_CALCULUS_PARAMS.natureVulnerabilityCoupling;
  const humanComponent = gamma * rawStress * DEFAULT_CALCULUS_PARAMS.humanDecisionCoupling * durationMultiplier;

  // Empirical shield & rebound weights
  const B = 2.0; 
  const Gamma = 2.0;

  if (humanComponent + natureComponent >= 0) {
    return (natureComponent + humanComponent) * Math.min(2.0, Math.sqrt(B));
  } else {
    return ((natureComponent + humanComponent) / Math.max(0.8, Math.sqrt(B))) * (1.0 + (Gamma - 1.0) * gamma);
  }
}

interface HindcastTransitionResult {
  fromYear: number;
  toYear: number;
  totalSeries: number;
  directionalHitCount: number;
  hitRatePercent: number;
  meanAbsoluteError: number;
  actualNetPulseChange: number;
  forecastNetPulseChange: number;
  pulseDirectionMatch: boolean;
  actualTurbulenceAtT1: number;
  forecastTurbulenceAtT1: number;
  layerBreakdown: {
    infraHitRate: number;
    humanHitRate: number;
    natureHitRate: number;
  };
}

export function runComprehensiveHindcast(): HindcastTransitionResult[] {
  const transitions = [
    { from: 1973, to: 1980 },
    { from: 1980, to: 1990 },
    { from: 1990, to: 2001 },
    { from: 2001, to: 2008 },
    { from: 2008, to: 2013 },
    { from: 2013, to: 2020 },
    { from: 2020, to: 2024 }
  ];

  const results: HindcastTransitionResult[] = [];

  for (const trans of transitions) {
    const deltaYears = trans.to - trans.from;
    let hitCount = 0;
    let absErrorSum = 0;

    let actualPulseSumT0 = 0;
    let actualPulseSumT1 = 0;
    let forecastPulseSumT1 = 0;

    let actualTurbSumT1 = 0;
    let forecastTurbSumT1 = 0;

    let infraHits = 0, infraTotal = 0;
    let humanHits = 0, humanTotal = 0;
    let natureHits = 0, natureTotal = 0;

    for (const s of FLEET_50_SERIES) {
      const s0 = computeScoreAtYear(s, trans.from);
      const s1Actual = computeScoreAtYear(s, trans.to);

      actualPulseSumT0 += s0;
      actualPulseSumT1 += s1Actual;
      actualTurbSumT1 += Math.abs(s1Actual);

      // Apply the exact Forecasting Engine formulation:
      const tau = s.defaultDurationYears;
      let s1Forecast = s0;

      if (s.layer === 'infrastructure') {
        infraTotal++;
        if (s0 > 0) {
          s1Forecast = s0 * (1.0 + 0.04 * deltaYears);
        } else {
          s1Forecast = s0 * Math.exp(-deltaYears / (tau * 1.5));
        }
      } else if (
        s.id === 's38-global-debt-gdp' ||
        s.id === 's36-central-bank-assets' ||
        s.id === 's46-forcibly-displaced'
      ) {
        humanTotal++;
        // Structural hysteresis
        s1Forecast = s0 * Math.exp(-deltaYears / (tau * 2.8));
      } else if (s.layer === 'nature') {
        natureTotal++;
        s1Forecast = s0 * Math.exp(-deltaYears / Math.max(1.5, tau * 0.85));
      } else {
        humanTotal++;
        s1Forecast = s0 * Math.exp(-deltaYears / Math.max(1.0, tau));
      }

      forecastPulseSumT1 += s1Forecast;
      forecastTurbSumT1 += Math.abs(s1Forecast);

      // Metric 1: Directional match of the delta
      const actualDelta = s1Actual - s0;
      const forecastDelta = s1Forecast - s0;

      const matchedDirection = (actualDelta >= 0 && forecastDelta >= 0) || (actualDelta < 0 && forecastDelta < 0);
      if (matchedDirection) {
        hitCount++;
        if (s.layer === 'infrastructure') infraHits++;
        else if (s.layer === 'nature') natureHits++;
        else humanHits++;
      }

      absErrorSum += Math.abs(s1Actual - s1Forecast);
    }

    const actualNetChange = actualPulseSumT1 - actualPulseSumT0;
    const forecastNetChange = forecastPulseSumT1 - actualPulseSumT0;

    results.push({
      fromYear: trans.from,
      toYear: trans.to,
      totalSeries: FLEET_50_SERIES.length,
      directionalHitCount: hitCount,
      hitRatePercent: parseFloat(((hitCount / FLEET_50_SERIES.length) * 100).toFixed(1)),
      meanAbsoluteError: parseFloat((absErrorSum / FLEET_50_SERIES.length).toFixed(3)),
      actualNetPulseChange: parseFloat(actualNetChange.toFixed(2)),
      forecastNetPulseChange: parseFloat(forecastNetChange.toFixed(2)),
      pulseDirectionMatch: (actualNetChange >= 0 && forecastNetChange >= 0) || (actualNetChange < 0 && forecastNetChange < 0),
      actualTurbulenceAtT1: parseFloat(actualTurbSumT1.toFixed(2)),
      forecastTurbulenceAtT1: parseFloat(forecastTurbSumT1.toFixed(2)),
      layerBreakdown: {
        infraHitRate: parseFloat(((infraHits / Math.max(1, infraTotal)) * 100).toFixed(1)),
        humanHitRate: parseFloat(((humanHits / Math.max(1, humanTotal)) * 100).toFixed(1)),
        natureHitRate: parseFloat(((natureHits / Math.max(1, natureTotal)) * 100).toFixed(1))
      }
    });
  }

  return results;
}

const hindcast = runComprehensiveHindcast();
console.log('=== HINDCASTING / HISTORICAL BACKTEST VERIFICATION ===');
console.table(hindcast.map(r => ({
  Transition: `${r.fromYear} -> ${r.toYear}`,
  'Hit Rate': `${r.hitRatePercent}% (${r.directionalHitCount}/${r.totalSeries})`,
  'MAE': r.meanAbsoluteError,
  'Actual Net Pulse': r.actualNetPulseChange,
  'Forecast Net Pulse': r.forecastNetPulseChange,
  'Net Match?': r.pulseDirectionMatch ? 'YES' : 'NO',
  'Infra Hit': `${r.layerBreakdown.infraHitRate}%`,
  'Human Hit': `${r.layerBreakdown.humanHitRate}%`,
  'Nature Hit': `${r.layerBreakdown.natureHitRate}%`
})));
