import {
  StandardTimeSeries,
  DiscoveredMotif,
  SurrogateNullTest,
  IntervalEmergenceAnalysis,
  DiscoveryExecutionResult
} from '../types';

/**
 * Z-normalize a numeric sub-sequence to zero-mean and unit-variance.
 */
export function zNormalize(subsequence: number[]): number[] {
  const n = subsequence.length;
  if (n === 0) return [];

  const mean = subsequence.reduce((acc, val) => acc + val, 0) / n;
  let variance = 0;
  for (let i = 0; i < n; i++) {
    variance += (subsequence[i] - mean) ** 2;
  }
  const std = Math.sqrt(variance / n);

  if (std < 1e-8) {
    return new Array(n).fill(0);
  }

  return subsequence.map((val) => (val - mean) / std);
}

/**
 * Calculate Euclidean distance between two equal-length z-normalized vectors.
 */
export function zEuclideanDistance(normA: number[], normB: number[]): number {
  const n = normA.length;
  let sumSq = 0;
  for (let i = 0; i < n; i++) {
    const diff = normA[i] - normB[i];
    sumSq += diff * diff;
  }
  return Math.sqrt(sumSq);
}

/**
 * Fisher-Yates random shuffle for surrogate null hypothesis generation.
 */
function shuffleArray<T>(array: T[]): T[] {
  const arr = [...array];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/**
 * Find the single minimal distance pair (motif) in an array of numbers with a sliding window w.
 * Uses temporal exclusion zone to prevent trivial self-matching.
 */
export function findMinimalMotifDistance(
  values: number[],
  windowSize: number,
  exclusionZone: number
): { distance: number; indexA: number; indexB: number } {
  const n = values.length;
  const numSubsequences = n - windowSize + 1;
  if (numSubsequences < 2) {
    return { distance: Infinity, indexA: -1, indexB: -1 };
  }

  // Pre-normalize all subsequences
  const normalizedSubs: number[][] = [];
  for (let i = 0; i < numSubsequences; i++) {
    normalizedSubs.push(zNormalize(values.slice(i, i + windowSize)));
  }

  let minDistance = Infinity;
  let bestA = 0;
  let bestB = 0;

  for (let i = 0; i < numSubsequences; i++) {
    for (let j = i + exclusionZone; j < numSubsequences; j++) {
      const dist = zEuclideanDistance(normalizedSubs[i], normalizedSubs[j]);
      if (dist < minDistance) {
        minDistance = dist;
        bestA = i;
        bestB = j;
      }
    }
  }

  return { distance: minDistance, indexA: bestA, indexB: bestB };
}

/**
 * Execute the Complete Neutral Discovery Engine Pipeline
 * 1. Matrix Profile Motif Discovery
 * 2. Multi-occurrence clustering
 * 3. Surrogate Null Model Hypothesis Testing
 * 4. Interval Emergence Analysis
 */
export function runNeutralDiscoveryPipeline(
  series: StandardTimeSeries,
  windowSize: number = 8,
  surrogatePermutations: number = 150
): DiscoveryExecutionResult {
  const startTime = performance.now();
  const rawValues = series.points.map((p) => p.value);
  const totalPoints = rawValues.length;

  // Window size safety clamp
  const w = Math.max(4, Math.min(windowSize, Math.floor(totalPoints / 2.5)));
  const exclusionZone = Math.max(2, Math.floor(w / 1.5));
  const numSubsequences = totalPoints - w + 1;

  // Step 1: Compute matrix profile and locate the minimal distance motifs
  const bestPair = findMinimalMotifDistance(rawValues, w, exclusionZone);

  const normalizedA = zNormalize(rawValues.slice(bestPair.indexA, bestPair.indexA + w));
  const normalizedB = zNormalize(rawValues.slice(bestPair.indexB, bestPair.indexB + w));

  // Max theoretical distance for z-normalized vectors of length w is sqrt(2w)
  const maxPossibleDist = Math.sqrt(2 * w);
  const similarityPct = Math.max(0, Math.min(100, Math.round((1 - bestPair.distance / maxPossibleDist) * 100)));

  // Scan all other subsequences that match this discovered shape
  const occurrenceThreshold = Math.max(bestPair.distance * 1.35, bestPair.distance + 0.35);
  const occurrences: Array<{ index: number; date: string; distanceToCentroid: number }> = [];

  for (let i = 0; i < numSubsequences; i++) {
    const normSub = zNormalize(rawValues.slice(i, i + w));
    const distA = zEuclideanDistance(normSub, normalizedA);
    const distB = zEuclideanDistance(normSub, normalizedB);
    const avgDist = (distA + distB) / 2;

    if (avgDist <= occurrenceThreshold) {
      // Check that it does not overlap an existing occurrence within exclusion zone
      const tooClose = occurrences.some((occ) => Math.abs(occ.index - i) < exclusionZone);
      if (!tooClose) {
        occurrences.push({
          index: i,
          date: series.points[i].date,
          distanceToCentroid: Number(avgDist.toFixed(3))
        });
      }
    }
  }

  // Sort occurrences chronologically
  occurrences.sort((a, b) => a.index - b.index);

  const discoveredMotif: DiscoveredMotif = {
    motifId: `MOTIF-W${w}-${bestPair.indexA}-${bestPair.indexB}`,
    windowSize: w,
    distance: Number(bestPair.distance.toFixed(4)),
    similarityPercentage: similarityPct,
    occurrenceA: {
      startIndex: bestPair.indexA,
      startDate: series.points[bestPair.indexA].date,
      endDate: series.points[bestPair.indexA + w - 1].date,
      rawValues: rawValues.slice(bestPair.indexA, bestPair.indexA + w),
      normalizedValues: normalizedA.map((v) => Number(v.toFixed(3)))
    },
    occurrenceB: {
      startIndex: bestPair.indexB,
      startDate: series.points[bestPair.indexB].date,
      endDate: series.points[bestPair.indexB + w - 1].date,
      rawValues: rawValues.slice(bestPair.indexB, bestPair.indexB + w),
      normalizedValues: normalizedB.map((v) => Number(v.toFixed(3)))
    },
    allOccurrences: occurrences
  };

  // Step 2: Surrogate Null Hypothesis Testing (Monte Carlo)
  const surrogateDistances: number[] = [];
  let countBetterOrEqual = 0;

  for (let p = 0; p < surrogatePermutations; p++) {
    const shuffled = shuffleArray(rawValues);
    const surrResult = findMinimalMotifDistance(shuffled, w, exclusionZone);
    surrogateDistances.push(surrResult.distance);
    if (surrResult.distance <= bestPair.distance) {
      countBetterOrEqual++;
    }
  }

  const surrMean = surrogateDistances.reduce((acc, v) => acc + v, 0) / surrogatePermutations;
  const surrVar =
    surrogateDistances.reduce((acc, v) => acc + (v - surrMean) ** 2, 0) / surrogatePermutations;
  const surrStd = Math.sqrt(surrVar) || 1e-6;

  // Z-score: How many standard deviations below random noise is our observed distance?
  const zScore = (surrMean - bestPair.distance) / surrStd;
  const pValue = (countBetterOrEqual + 1) / (surrogatePermutations + 1);

  let verdict: SurrogateNullTest['verdict'];
  let scientificNote: string;

  if (pValue < 0.05 && zScore >= 2.0) {
    verdict = 'CONFIRMED_NON_RANDOM_STRUCTURE';
    scientificNote = `تم رفض فرضية العشوائية (Null Hypothesis) بمستوى دلالة p=${pValue.toFixed(
      4
    )} و Z=${zScore.toFixed(
      2
    )}σ. المسافة بين المقاطع المتكررة في السلسلة الأصلية أقل بكثير من أي توزيع عشوائي للبيانات نفسها، مما يؤكد وجود بنية زمنية داخلية حقيقية.`;
  } else if (zScore >= 1.2) {
    verdict = 'INCONCLUSIVE_WEAK_SIGNAL';
    scientificNote = `إشارة ضعيفة إلى متوسطة (Z=${zScore.toFixed(2)}σ، p=${pValue.toFixed(
      4
    )}). النمط موجود لكنه لا يبتعد إحصائياً بصورة قاطعة عن الصدفة العشوائية بموجب عينة التدقيق.`;
  } else {
    verdict = 'REJECTED_AS_STOCHASTIC_NOISE';
    scientificNote = `فشل في رفض فرضية العشوائية (p=${pValue.toFixed(4)}، Z=${zScore.toFixed(
      2
    )}σ). المقاطع المتكررة في السلسلة لا تختلف إحصائياً عن المقاطع الناتجة من خلط البيانات عشوائياً.`;
  }

  const surrogateTestResult: SurrogateNullTest = {
    permutationsCount: surrogatePermutations,
    observedMotifDistance: Number(bestPair.distance.toFixed(4)),
    surrogateDistancesMean: Number(surrMean.toFixed(4)),
    surrogateDistancesStd: Number(surrStd.toFixed(4)),
    zScore: Number(zScore.toFixed(2)),
    pValue: Number(pValue.toFixed(4)),
    isStatisticallySignificant: pValue < 0.05 && zScore >= 2.0,
    verdict,
    scientificNote
  };

  // Step 3: Interval Emergence Analysis (Zero A-Priori Assumption)
  let intervalEmergence: IntervalEmergenceAnalysis | undefined = undefined;

  if (occurrences.length >= 2) {
    const dates = occurrences.map((occ) => occ.date);
    const msIntervals: number[] = [];

    for (let i = 0; i < occurrences.length - 1; i++) {
      const t1 = series.points[occurrences[i].index].timestamp;
      const t2 = series.points[occurrences[i + 1].index].timestamp;
      const deltaDays = Math.round(Math.abs(t2 - t1) / (1000 * 60 * 60 * 24));
      msIntervals.push(deltaDays);
    }

    const ratios: number[] = [];
    for (let i = 0; i < msIntervals.length - 1; i++) {
      if (msIntervals[i] > 0) {
        ratios.push(Number((msIntervals[i + 1] / msIntervals[i]).toFixed(3)));
      }
    }

    const meanInterval = msIntervals.reduce((a, b) => a + b, 0) / msIntervals.length;
    const meanRatio = ratios.length > 0 ? ratios.reduce((a, b) => a + b, 0) / ratios.length : 1.0;
    const ratioVar =
      ratios.length > 0
        ? ratios.reduce((a, b) => a + (b - meanRatio) ** 2, 0) / ratios.length
        : 0;
    const ratioStd = Math.sqrt(ratioVar);

    let classification: IntervalEmergenceAnalysis['classification'];
    let narrative: string;

    if (ratios.length === 0) {
      classification = 'PERIODIC_STABLE';
      narrative = `تم رصد ظهورين للمقطع بفاصل زمني قدره ${Math.round(
        meanInterval
      )} يوماً (${(meanInterval / 365.25).toFixed(1)} سنة). يتطلب قياس التغير في الفواصل رصد ظهور ثالث على الأقل.`;
    } else if (ratioStd < 0.18 && Math.abs(meanRatio - 1.0) <= 0.2) {
      classification = 'PERIODIC_STABLE';
      narrative = `الفواصل الزمنية تظهر استقراراً دورياً منتظماً (Harmonic Periodicity) بمتوسط فاصل قدره ${(
        meanInterval / 365.25
      ).toFixed(1)} سنة وبنسبة تأرجح حول الوحدة (${meanRatio.toFixed(2)} ± ${ratioStd.toFixed(
        2
      )}). لا يوجد تقلص أو تمدد منهجي.`;
    } else if (meanRatio < 0.85 && ratios.every((r) => r < 1.05)) {
      classification = 'SYSTEMATIC_CONTRACTION';
      narrative = `الفواصل الزمنية تظهر انكماشاً متسارعاً عبر الزمن (Contraction Behavior). متوسط نسبة الفاصل اللاحق إلى السابق هي ${meanRatio.toFixed(
        3
      )} ± ${ratioStd.toFixed(2)}. هذا النمط يشير إلى تسارع وتيرة ظهور الهيكل.`;
    } else if (meanRatio > 1.15 && ratios.every((r) => r > 0.95)) {
      classification = 'SYSTEMATIC_EXPANSION';
      narrative = `الفواصل الزمنية تتباعد بشكل متزايد (Temporal Expansion). متوسط النسبة هو ${meanRatio.toFixed(
        3
      )}. الهيكل يتكرر على فترات متباعدة بشكل تدريجي.`;
    } else {
      classification = 'STOCHASTIC_DRIFT';
      narrative = `الفواصل الزمنية بين مرات الظهور لا تتبع نسبة ثابتة (تشتت عالي: انحراف معياري ${ratioStd.toFixed(
        2
      )} حول متوسط ${meanRatio.toFixed(2)}). توزع الفواصل يبدو عشوائياً أو شبه دوري غير مقيد بنسبة محددة.`;
    }

    intervalEmergence = {
      timestamps: dates,
      rawIntervalsDays: msIntervals,
      intervalRatios: ratios,
      meanIntervalDays: Math.round(meanInterval),
      meanRatio: Number(meanRatio.toFixed(3)),
      ratioStdDev: Number(ratioStd.toFixed(3)),
      classification,
      candidateFormulaDescription: narrative
    };
  }

  const executionTimeMs = Number((performance.now() - startTime).toFixed(1));

  return {
    seriesId: series.id,
    seriesName: series.name,
    totalPoints,
    windowSize: w,
    executionTimeMs,
    matrixProfileMinDistance: Number(bestPair.distance.toFixed(4)),
    motifs: [discoveredMotif],
    surrogateTest: surrogateTestResult,
    intervalEmergence
  };
}
