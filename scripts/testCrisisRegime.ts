/**
 * Testing Thresholded Non-linear Crisis Jump formulation:
 * In general times (normal or mild stress), systems follow F3 (accumulation + long-decay).
 * ONLY when a verified systemic crisis regime occurs (Vuln > 0.50, as in 2008 post-Lehman collapse),
 * a crisis mode triggers for financial/policy variables, while preserving normal periods.
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

// Check if a starting year has extreme crisis indicators:
function getCrisisRegime(year: number): boolean {
  // s36 (central bank balance sheet surge) or extreme policy uncertainty s40 > 0.7
  const s40 = FLEET_50_SERIES.find(s => s.id === 's40-policy-uncertainty')?.benchmarks.find(b => b.year === year)?.normalizedStress || 0;
  const s34 = FLEET_50_SERIES.find(s => s.id === 's34-us-10y-treasury')?.benchmarks.find(b => b.year === year)?.normalizedStress || 0;
  const s38 = FLEET_50_SERIES.find(s => s.id === 's38-global-debt-gdp')?.benchmarks.find(b => b.year === year)?.normalizedStress || 0;

  const crisisScore = -s40 * 0.4 - s34 * 0.3 - s38 * 0.3;
  return crisisScore > 0.52;
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

console.log('Regimes identified:');
transitions.forEach(t => {
  console.log(`${t.from}: Crisis Regime = ${getCrisisRegime(t.from)}`);
});
