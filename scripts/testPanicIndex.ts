/**
 * Test script: Panic & Uncertainty Index (Phi_t) across all 7 transitions
 * Grounded on empirical data:
 * 1. Policy Uncertainty (s40)
 * 2. Debt & Central Bank acceleration (s36, s38)
 * 3. Volatility / 2nd derivative of human system stress
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

/**
 * Compute empirical Fear & Uncertainty Index Phi(year) in [0, 1]
 * Derived strictly from actual series values:
 * - Policy uncertainty normalized stress
 * - Global debt / GDP acceleration
 * - Central bank asset spikes
 */
function computeFearAndUncertaintyIndex(year: number): number {
  const s40 = FLEET_50_SERIES.find(s => s.id === 's40-policy-uncertainty');
  const s38 = FLEET_50_SERIES.find(s => s.id === 's38-global-debt-gdp');
  const s36 = FLEET_50_SERIES.find(s => s.id === 's36-central-bank-assets');

  const uVal = s40?.benchmarks.find(b => b.year === year)?.normalizedStress || 0.0;
  const debtVal = s38?.benchmarks.find(b => b.year === year)?.normalizedStress || 0.0;
  const cbVal = s36?.benchmarks.find(b => b.year === year)?.normalizedStress || 0.0;

  // Raw panic score based on absolute negative stress or high volatility
  const panicSignal = Math.max(0, -uVal * 0.4) + Math.max(0, -debtVal * 0.35) + Math.max(0, -cbVal * 0.25);
  
  // Sigmoid bounding into [0, 1]
  const phi = 1.0 / (1.0 + Math.exp(-(panicSignal - 0.2) * 4.0));
  return parseFloat(phi.toFixed(3));
}

export function testComparativeFramework() {
  const transitions = [
    { from: 1973, to: 1980 },
    { from: 1980, to: 1990 },
    { from: 1990, to: 2001 },
    { from: 2001, to: 2008 },
    { from: 2008, to: 2013 },
    { from: 2013, to: 2020 },
    { from: 2020, to: 2024 }
  ];

  console.log('=== FEAR & UNCERTAINTY INDEX PHI(t) VALUES ===');
  transitions.forEach(t => {
    console.log(`Year ${t.from}: Phi = ${computeFearAndUncertaintyIndex(t.from)} | Year ${t.to}: Phi = ${computeFearAndUncertaintyIndex(t.to)}`);
  });

  const comparisons: any[] = [];

  for (const trans of transitions) {
    const deltaYears = trans.to - trans.from;
    const phiT0 = computeFearAndUncertaintyIndex(trans.from);

    let hitsWithoutPhi = 0;
    let hitsWithPhi = 0;
    let maeWithoutPhi = 0;
    let maeWithPhi = 0;

    for (const s of FLEET_50_SERIES) {
      const s0 = computeRawImpact(s, trans.from);
      const s1Actual = computeRawImpact(s, trans.to);
      const tau = s.defaultDurationYears;

      // 1. Without Phi (Previous baseline)
      let s1Prev = s0;
      if (s.layer === 'infrastructure') {
        if (s0 > 0) s1Prev = s0 * (1.0 + 0.04 * deltaYears);
        else s1Prev = s0 * Math.exp(-deltaYears / (tau * 1.5));
      } else if (s.id === 's38-global-debt-gdp' || s.id === 's36-central-bank-assets' || s.id === 's46-forcibly-displaced') {
        s1Prev = s0 * Math.exp(-deltaYears / (tau * 2.8));
      } else if (s.layer === 'nature') {
        s1Prev = s0 * Math.exp(-deltaYears / Math.max(1.5, tau * 0.85));
      } else {
        s1Prev = s0 * Math.exp(-deltaYears / Math.max(1.0, tau));
      }

      // 2. With Phi Dynamic Modulation
      let s1Mod = s0;
      // Capital growth slows down when fear/uncertainty is high
      const effectiveInfraGrowth = 0.04 * Math.max(0.1, 1.0 - 1.2 * phiT0);
      // Effective human decision time horizon collapses when fear is high
      const tauHumanEffective = Math.max(0.4, tau * (1.0 - 0.65 * phiT0));

      if (s.layer === 'infrastructure') {
        if (s0 > 0) {
          s1Mod = s0 * (1.0 + effectiveInfraGrowth * deltaYears);
        } else {
          s1Mod = s0 * Math.exp(-deltaYears / (tau * 1.5));
        }
      } else if (s.id === 's38-global-debt-gdp' || s.id === 's36-central-bank-assets' || s.id === 's46-forcibly-displaced') {
        // Debt hysteresis stretches even longer during high uncertainty
        const debtHysteresisDynamic = 2.8 * (1.0 + 0.5 * phiT0);
        s1Mod = s0 * Math.exp(-deltaYears / (tau * debtHysteresisDynamic));
      } else if (s.layer === 'nature') {
        s1Mod = s0 * Math.exp(-deltaYears / Math.max(1.5, tau * 0.85));
      } else {
        s1Mod = s0 * Math.exp(-deltaYears / tauHumanEffective);
      }

      const actualDelta = s1Actual - s0;
      const prevDelta = s1Prev - s0;
      const modDelta = s1Mod - s0;

      if ((actualDelta >= 0 && prevDelta >= 0) || (actualDelta < 0 && prevDelta < 0)) hitsWithoutPhi++;
      if ((actualDelta >= 0 && modDelta >= 0) || (actualDelta < 0 && modDelta < 0)) hitsWithPhi++;

      maeWithoutPhi += Math.abs(s1Actual - s1Prev);
      maeWithPhi += Math.abs(s1Actual - s1Mod);
    }

    comparisons.push({
      Transition: `${trans.from} -> ${trans.to}`,
      'Phi(t0)': phiT0,
      'Hit Rate (Before)': `${((hitsWithoutPhi / 50) * 100).toFixed(1)}%`,
      'Hit Rate (With Phi)': `${((hitsWithPhi / 50) * 100).toFixed(1)}%`,
      'MAE (Before)': (maeWithoutPhi / 50).toFixed(3),
      'MAE (With Phi)': (maeWithPhi / 50).toFixed(3),
      'Improvement': hitsWithPhi >= hitsWithoutPhi ? '✅ IMPROVED / STABLE' : '❌ REGRESSED'
    });
  }

  console.log('\n=== COMPREHENSIVE HISTORICAL EVALUATION: ALL 7 TRANSITIONS ===');
  console.table(comparisons);
}

testComparativeFramework();
