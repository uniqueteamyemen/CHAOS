/**
 * Detailed error breakdown to see where the 2008 & 2001 errors went
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

// Check transition 2001 -> 2008 in detail
const t0 = 2001, t1 = 2008;
const deltaYears = 7;
console.log(`=== DETAILED SERIES DELTAS FOR 2001 -> 2008 ===`);

const misses: any[] = [];
for (const s of FLEET_50_SERIES) {
  const s0 = computeRawImpact(s, t0);
  const s1 = computeRawImpact(s, t1);
  const actualDelta = s1 - s0;
  
  // Forecast:
  const tau = s.defaultDurationYears;
  let s1Pred = s0;
  if (s.layer === 'infrastructure') {
    s1Pred = s0 > 0 ? s0 * (1 + 0.04 * deltaYears) : s0 * Math.exp(-deltaYears / (tau * 1.5));
  } else if (s.id === 's38-global-debt-gdp' || s.id === 's36-central-bank-assets' || s.id === 's46-forcibly-displaced') {
    s1Pred = s0 * Math.exp(-deltaYears / (tau * 2.8));
  } else if (s.layer === 'nature') {
    s1Pred = s0 * Math.exp(-deltaYears / Math.max(1.5, tau * 0.85));
  } else {
    s1Pred = s0 * Math.exp(-deltaYears / Math.max(1.0, tau));
  }
  const predDelta = s1Pred - s0;
  const isHit = (actualDelta >= 0 && predDelta >= 0) || (actualDelta < 0 && predDelta < 0);
  if (!isHit) {
    misses.push({
      id: s.id,
      name: s.nameAr,
      layer: s.layer,
      s0: s0.toFixed(2),
      s1Actual: s1.toFixed(2),
      actualDelta: actualDelta.toFixed(2),
      predDelta: predDelta.toFixed(2),
    });
  }
}

console.log(`Total misses in 2001 -> 2008: ${misses.length}/50`);
console.table(misses.slice(0, 15));
