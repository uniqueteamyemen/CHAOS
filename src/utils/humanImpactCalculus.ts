// src/utils/humanImpactCalculus.ts
// Mathematical Engine for Governed Human Impact Dynamics across 50 Time Series
// Implements the Non-Absolute Human-Centric Calculus agreed upon.

import { FLEET_50_SERIES, FleetSeriesItem } from '../data/fleet50Series';

export interface CalculusParameters {
  natureVulnerabilityCoupling: number; // How much nature affects humans (default: 0.15)
  humanDecisionCoupling: number;       // How much human decisions drive strain (default: 0.85)
  bufferingShieldPower: number;        // Effect of era technology/food buffer B(t) (default: 1.0)
  reboundCostTax: number;              // Extra penalty for human interventions Gamma(t) (default: 1.0)
  targetYear: number;                  // 1973, 1980, 1990, 2001, 2008, 2020, 2024
}

export const DEFAULT_CALCULUS_PARAMS: CalculusParameters = {
  natureVulnerabilityCoupling: 0.15,
  humanDecisionCoupling: 0.85,
  bufferingShieldPower: 1.0,
  reboundCostTax: 1.0,
  targetYear: 2008
};

/**
 * Era Buffering Shield B(t):
 * Normalizes human adaptation capacity over time (1970 baseline = 1.0).
 * Driven by electricity access, internet, medicine, agricultural yield.
 */
export function getEraBufferingShield(year: number, power: number = 1.0): number {
  // Approximate empirical capacity factor
  const baseYield: Record<number, number> = {
    1973: 1.0,
    1980: 1.25,
    1990: 1.60,
    2001: 2.10,
    2008: 2.75,
    2020: 3.80,
    2024: 4.10
  };
  const raw = baseYield[year] || 2.5;
  return Math.pow(raw, power);
}

/**
 * Rebound Cost Tax Gamma(t):
 * Captures the side effects of human intervention (debt, inflation, environmental degradation).
 */
export function getReboundCostMultiplier(year: number, taxScale: number = 1.0): number {
  const baseTaxes: Record<number, number> = {
    1973: 1.10,
    1980: 1.25,
    1990: 1.35,
    2001: 1.50,
    2008: 1.85,
    2020: 2.40,
    2024: 2.55
  };
  const raw = baseTaxes[year] || 1.5;
  return 1.0 + (raw - 1.0) * taxScale;
}

export interface SeriesCalculusResult {
  series: FleetSeriesItem;
  rawStress: number;
  gamma: number;
  tau: number;
  naturePortion: number;
  humanPortion: number;
  bufferedImpact: number;
  finalScore: number; // Signed impact on human well-being
  absoluteMagnitude: number; // Strain energy |Score|
}

export interface FleetSnapshotAnalysis {
  year: number;
  bufferingShield: number;
  reboundMultiplier: number;
  items: SeriesCalculusResult[];
  // Aggregate Metrics
  netHumanPulse: number;          // Sum of signed scores (+ = net enablement, - = net strain)
  totalTurbulenceEnergy: number;  // Sum of absolute magnitudes (total upheaval)
  layerShares: {
    naturePercentage: number;
    infrastructurePercentage: number;
    humanSystemPercentage: number;
  };
  strainDistribution: {
    positiveCount: number; // Benefit/growth
    negativeCount: number; // Stress/destruction
    neutralCount: number;  // Near zero
  };
}

/**
 * Calculates the exact human impact scores for all 50 series at a specific benchmark year
 */
export function computeFleetCalculus(params: CalculusParameters): FleetSnapshotAnalysis {
  const B = getEraBufferingShield(params.targetYear, params.bufferingShieldPower);
  const Gamma = getReboundCostMultiplier(params.targetYear, params.reboundCostTax);

  let totalNatureAbs = 0;
  let totalInfraAbs = 0;
  let totalHumanAbs = 0;

  let posCount = 0;
  let negCount = 0;
  let neuCount = 0;

  const results: SeriesCalculusResult[] = FLEET_50_SERIES.map((series) => {
    // Find benchmark or fallback
    const benchmark = series.benchmarks.find((b) => b.year === params.targetYear) ||
      series.benchmarks[series.benchmarks.length - 1];

    const rawStress = benchmark.normalizedStress;
    const gamma = series.gamma;
    const tau = params.targetYear === 2008 ? series.snapshot2008.observedDurationYears : series.defaultDurationYears;
    const durationMultiplier = Math.sqrt(Math.max(0.5, tau / 3.0)); // Square-root temporal scaling to avoid unbounded explosion

    // Split into Nature vs Human components
    const natureComponent = (1.0 - gamma) * rawStress * params.natureVulnerabilityCoupling;
    const humanComponent = gamma * rawStress * params.humanDecisionCoupling * durationMultiplier;

    // Combine and apply era buffering and feedback taxes
    // Positive stress (enablement) is amplified by buffer B; negative stress (strain) is attenuated by buffer B, but burdened by Gamma
    let bufferedImpact: number;
    if (humanComponent + natureComponent >= 0) {
      bufferedImpact = (natureComponent + humanComponent) * Math.min(2.0, Math.sqrt(B));
    } else {
      bufferedImpact = ((natureComponent + humanComponent) / Math.max(0.8, Math.sqrt(B))) * (1.0 + (Gamma - 1.0) * gamma);
    }

    const finalScore = parseFloat(bufferedImpact.toFixed(3));
    const absoluteMagnitude = parseFloat(Math.abs(finalScore).toFixed(3));

    // Track layer shares
    if (series.layer === 'nature') totalNatureAbs += absoluteMagnitude;
    else if (series.layer === 'infrastructure') totalInfraAbs += absoluteMagnitude;
    else totalHumanAbs += absoluteMagnitude;

    // Track classification
    if (finalScore > 0.08) posCount++;
    else if (finalScore < -0.08) negCount++;
    else neuCount++;

    return {
      series,
      rawStress,
      gamma,
      tau,
      naturePortion: parseFloat(natureComponent.toFixed(3)),
      humanPortion: parseFloat(humanComponent.toFixed(3)),
      bufferedImpact,
      finalScore,
      absoluteMagnitude
    };
  });

  const totalAbsEnergy = totalNatureAbs + totalInfraAbs + totalHumanAbs || 1.0;
  const netPulse = results.reduce((acc, curr) => acc + curr.finalScore, 0);

  return {
    year: params.targetYear,
    bufferingShield: parseFloat(B.toFixed(2)),
    reboundMultiplier: parseFloat(Gamma.toFixed(2)),
    items: results,
    netHumanPulse: parseFloat(netPulse.toFixed(2)),
    totalTurbulenceEnergy: parseFloat(totalAbsEnergy.toFixed(2)),
    layerShares: {
      naturePercentage: parseFloat(((totalNatureAbs / totalAbsEnergy) * 100).toFixed(1)),
      infrastructurePercentage: parseFloat(((totalInfraAbs / totalAbsEnergy) * 100).toFixed(1)),
      humanSystemPercentage: parseFloat(((totalHumanAbs / totalAbsEnergy) * 100).toFixed(1))
    },
    strainDistribution: {
      positiveCount: posCount,
      negativeCount: negCount,
      neutralCount: neuCount
    }
  };
}

/**
 * Historical Backtesting & Past-Forecasting:
 * Evaluates the 7 major historical checkpoints (1973, 1980, 1990, 2001, 2008, 2020, 2024)
 * to test if the formula captures historical structural resets without retro-fitting.
 */
export interface MultiYearTrajectoryPoint {
  year: number;
  labelAr: string;
  netHumanPulse: number;
  totalTurbulenceEnergy: number;
  naturePercentage: number;
  infrastructurePercentage: number;
  humanSystemPercentage: number;
  deltaYearsFromPrior?: number;
  historicalEventAr: string;
}

export const HISTORICAL_CHECKPOINTS: { year: number; labelAr: string; eventAr: string }[] = [
  { year: 1973, labelAr: '1973: صدمة النفط الأولى', eventAr: 'حرب أكتوبر، حظر تصدير النفط، وكسر نظام بريتون وودز المالي.' },
  { year: 1980, labelAr: '1980: ذروة التضخم والركود التضخمي', eventAr: 'الثورة الإيرانية، حرب الخليج الأولى، ورفع فولكر للفائدة إلى 20%.' },
  { year: 1990, labelAr: '1990: إعادة التشكيل الجيوسياسي', eventAr: 'سقوط الستار الحديدي، حرب الخليج الثانية، وبداية العولمة الأحادية.' },
  { year: 2001, labelAr: '2001: انفجار الدوت كوم وهجمات سبتمبر', eventAr: 'انهيار أسهم التقنية، أحداث 11 سبتمبر، وبدء حقبة الفائدة المنخفضة.' },
  { year: 2008, labelAr: '2008: الأزمة المالية الكبرى (نقطة الالتقاء)', eventAr: 'انهيار ليمان براذرز، ذروة النفط 147$، قفزة التضخم، والتيسير الكمي.' },
  { year: 2020, labelAr: '2020: صدمة جائحة كوفيد-19', eventAr: 'الإغلاق الشامل للطيران والحركة، شلل التجارة، وضخ سيولة غير مسبوق.' },
  { year: 2024, labelAr: '2024: التشكيل المتعدد الأقطاب والذكاء الاصطناعي', eventAr: 'انفجار التضخم المالي بعد الجائحة، الصراعات الإقليمية، وثورة الذكاء الاصطناعي.' }
];

export function computeMultiYearTrajectory(
  params: Omit<CalculusParameters, 'targetYear'>
): MultiYearTrajectoryPoint[] {
  let priorYear: number | undefined = undefined;

  return HISTORICAL_CHECKPOINTS.map((cp) => {
    const snap = computeFleetCalculus({ ...params, targetYear: cp.year });
    const delta = priorYear !== undefined ? cp.year - priorYear : undefined;
    priorYear = cp.year;

    return {
      year: cp.year,
      labelAr: cp.labelAr,
      netHumanPulse: snap.netHumanPulse,
      totalTurbulenceEnergy: snap.totalTurbulenceEnergy,
      naturePercentage: snap.layerShares.naturePercentage,
      infrastructurePercentage: snap.layerShares.infrastructurePercentage,
      humanSystemPercentage: snap.layerShares.humanSystemPercentage,
      deltaYearsFromPrior: delta,
      historicalEventAr: cp.eventAr
    };
  });
}
