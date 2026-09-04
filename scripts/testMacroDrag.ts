/**
 * Systematic evaluation:
 * Testing the Macro Cross-Coupling Formulation F4 across all 7 transitions.
 * If Macro Vulnerability / Panic is elevated at t0:
 * - Human decision series experience a directional strain drag proportional to their gamma and vulnerability
 * - Infra expansion slows
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

function getVulnerabilityAtT0(t0: number): number {
  const yieldS = FLEET_50_SERIES.find(s => s.id === 's34-us-10y-treasury')?.benchmarks.find(b => b.year === t0)?.normalizedStress || 0;
  const debt0 = FLEET_50_SERIES.find(s => s.id === 's38-global-debt-gdp')?.benchmarks.find(b => b.year === t0)?.normalizedStress || 0;
  const uncert = FLEET_50_SERIES.find(s => s.id === 's40-policy-uncertainty')?.benchmarks.find(b => b.year === t0)?.normalizedStress || 0;

  // Composite Vulnerability Index from t0 state only:
  const raw = Math.max(0, -yieldS * 0.4 - debt0 * 0.4 - uncert * 0.2);
  return parseFloat(raw.toFixed(3));
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

console.log('=== COMPARING F3 (PREVIOUS) VS F4 (WITH SYSTEMIC VULNERABILITY / PANIC DRAG) ===');

const rows = transitions.map(t => {
  const deltaYears = t.to - t.from;
  const vulnT0 = getVulnerabilityAtT0(t.from);

  let hitCountF3 = 0;
  let hitCountF4 = 0;
  let maeF3 = 0;
  let maeF4 = 0;

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

    // F4 With Systemic Vulnerability Drag:
    // When systemic vulnerability is high at t0, human decisions face an adverse shift (-0.12 * vulnT0 * gamma),
    // and infra growth rate is moderated.
    let s1F4 = s0;
    const drag = vulnT0 > 0.2 ? -0.15 * vulnT0 * s.gamma * Math.min(2.0, deltaYears / 5.0) : 0;
    const infraGrowthRate = 0.04 * Math.max(0.2, 1.0 - 1.2 * vulnT0);

    if (s.layer === 'infrastructure') {
      s1F4 = s0 > 0 ? s0 * (1 + infraGrowthRate * deltaYears) + drag * 0.5 : s0 * Math.exp(-deltaYears / (tau * 1.5));
    } else if (s.id === 's38-global-debt-gdp' || s.id === 's36-central-bank-assets' || s.id === 's46-forcibly-displaced') {
      s1F4 = s0 * Math.exp(-deltaYears / (tau * 2.8)) + drag;
    } else if (s.layer === 'nature') {
      s1F4 = s0 * Math.exp(-deltaYears / Math.max(1.5, tau * 0.85));
    } else {
      s1F4 = s0 * Math.exp(-deltaYears / Math.max(1.0, tau)) + drag;
    }

    const deltaF3 = s1F3 - s0;
    const deltaF4 = s1F4 - s0;

    if ((actualDelta >= 0 && deltaF3 >= 0) || (actualDelta < 0 && deltaF3 < 0)) hitCountF3++;
    if ((actualDelta >= 0 && deltaF4 >= 0) || (actualDelta < 0 && deltaF4 < 0)) hitCountF4++;

    maeF3 += Math.abs(s1 - s1F3);
    maeF4 += Math.abs(s1 - s1F4);
  }

  return {
    Transition: `${t.from} -> ${t.to}`,
    'Vuln(t0)': vulnT0,
    'F3 Hit Rate': `${((hitCountF3 / 50) * 100).toFixed(1)}%`,
    'F4 Hit Rate': `${((hitCountF4 / 50) * 100).toFixed(1)}%`,
    'F3 MAE': (maeF3 / 50).toFixed(3),
    'F4 MAE': (maeF4 / 50).toFixed(3),
    'Outcome': hitCountF4 >= hitCountF3 ? (hitCountF4 > hitCountF3 ? '🌟 GAIN' : '✅ NEUTRAL') : '⚠️ DROP'
  };
});

console.table(rows);
