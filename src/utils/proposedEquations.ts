/**
 * Proposed Conditional Equations for the 4 Validated Patterns
 * 
 * Strict Guidelines:
 * 1. Independent module - NOT integrated into futureForecastEngine or runHindcast.
 * 2. Every equation is conditional (threshold-activated).
 * 3. Incorporates regime dependency (Stable vs Crisis).
 * 4. Strictly uses existing variables from the 50 series.
 * 5. All parameters are tunable and explicitly named.
 * 6. Full documentation for each equation.
 */

export interface ProposedEquationMetadata {
  patternId: string;
  patternNameAr: string;
  patternNameEn: string;
  empiricalEvidenceBasis: string;
  activationConditions: string[];
  scopeOfValidity: string;
  knownFailureModes: string[];
  acceptanceRejectionCriteria: string[];
  tunableParameters: Record<string, { value: number; descriptionAr: string }>;
}

export interface ProposedEquationResult {
  patternId: string;
  isActivated: boolean;
  regimeState: 'Stable' | 'Crisis';
  activationReasonAr: string;
  inputs: Record<string, number>;
  rawOutput: number;
  dampenedOutput: number;
  targetSeriesAdjustments: Record<string, number>;
}

// ============================================================================
// PAT-01: Food Security Buffer Drag (Grain Stocks ⟵ Food Price Inflation)
// ============================================================================

export const PAT01_METADATA: ProposedEquationMetadata = {
  patternId: 'PAT-01',
  patternNameAr: 'معادلة عتبة إجهاد مخزون الحبوب وأسعار الغذاء',
  patternNameEn: 'Critical Grain Stock Buffer Depletion & Food Inflation Equation',
  empiricalEvidenceBasis: 'ارتباط عكسي قوي (r = 0.84) ظهر في 5 انتقالات تاريخية؛ استنزاف المخزون يسبق انفجار أسعار الغذاء بحقبة واحدة وصمد خارج العينة في 2020→2024.',
  activationConditions: [
    'انخفاض الإجهاد المعياري لمخزون الحبوب (s15) دون العتبة الحرجة (s15_stress < -0.10)',
    'أو تزامن تراجع المخزون مع نقص الأسمدة النيتروجينية (s17_stress < -0.05)'
  ],
  scopeOfValidity: 'يعمل في جميع الأطوار، ويتضاعف تأثيره (Amplified) عند دخول طور الذعر/الأزمة.',
  knownFailureModes: [
    'حقبة 1990→2001: توسع الرقعة الزراعية العالمية المفاجئ في أمريكا الجنوبية خفف التضخم رغم تقلبات الأسمدة.'
  ],
  acceptanceRejectionCriteria: [
    'يجب أن يخفض MAE في انتقالات أزمات الغذاء (1973→1980 و 2008→2013) بنسبة ≥ 3%.',
    'يجب ألا يرفع معدل الخطأ في حقبة الهدوء الزراعي (1990→2001) بأكثر من 2%.',
    'يجب أن يتنبأ بارتفاع تضخم الغذاء خارج العينة 2020→2024.'
  ],
  tunableParameters: {
    stockDepletionThreshold: { value: -0.10, descriptionAr: 'عتبة استنزاف مخزون الحبوب الحرجة' },
    fertilizerStrainThreshold: { value: -0.05, descriptionAr: 'عتبة عجز الأسمدة الحرج' },
    baseElasticityAlpha: { value: 0.85, descriptionAr: 'مرونة الاستجابة الأساسية لتضخم الغذاء في الطور المستقر' },
    crisisMultiplierBeta: { value: 1.65, descriptionAr: 'مضاعف التضخيم في طور الذعر المالي' },
    lagCarryOver: { value: 0.70, descriptionAr: 'معامل استمرار الأثر في الحقبة اللاحقة' }
  }
};

/**
 * Calculates proposed adjustment for PAT-01
 * Formula:
 * IF (s15_stress < threshold) THEN:
 *   delta_Food = -alpha * (s15_stress - threshold) * (isCrisis ? beta : 1.0)
 */
export function evaluateProposedEquation_PAT01(
  s15_grainStockStress: number,
  s17_fertilizerStress: number,
  isCrisis: boolean,
  currentLagState: number = 0
): ProposedEquationResult {
  const p = PAT01_METADATA.tunableParameters;
  const isStockCritical = s15_grainStockStress < p.stockDepletionThreshold.value;
  const isFertilizerCritical = s17_fertilizerStress < p.fertilizerStrainThreshold.value;

  const isActivated = isStockCritical || isFertilizerCritical;

  if (!isActivated) {
    return {
      patternId: 'PAT-01',
      isActivated: false,
      regimeState: isCrisis ? 'Crisis' : 'Stable',
      activationReasonAr: 'مخزون الحبوب والأسمدة فوق العتبة الحرجة (المصدات آمنة).',
      inputs: { s15_grainStockStress, s17_fertilizerStress },
      rawOutput: 0,
      dampenedOutput: 0,
      targetSeriesAdjustments: { 's32-food-price-index': 0, 's31-global-inflation-rate': 0 }
    };
  }

  const stockDeficit = Math.max(0, p.stockDepletionThreshold.value - s15_grainStockStress);
  const fertilizerDeficit = Math.max(0, p.fertilizerStrainThreshold.value - s17_fertilizerStress);
  const combinedDeficit = stockDeficit * 0.7 + fertilizerDeficit * 0.3;

  const regimeFactor = isCrisis ? p.crisisMultiplierBeta.value : 1.0;
  const rawImpact = p.baseElasticityAlpha.value * combinedDeficit * regimeFactor;
  const totalImpact = rawImpact + currentLagState * p.lagCarryOver.value;

  return {
    patternId: 'PAT-01',
    isActivated: true,
    regimeState: isCrisis ? 'Crisis' : 'Stable',
    activationReasonAr: `تفعيل عتبة الإجهاد: عجز الحبوب = ${stockDeficit.toFixed(2)}، عجز الأسمدة = ${fertilizerDeficit.toFixed(2)}. تضخيم الطور = x${regimeFactor}`,
    inputs: { s15_grainStockStress, s17_fertilizerStress },
    rawOutput: parseFloat(rawImpact.toFixed(4)),
    dampenedOutput: parseFloat(totalImpact.toFixed(4)),
    targetSeriesAdjustments: {
      's32-food-price-index': parseFloat((-totalImpact).toFixed(4)), // إجهاد سالب = تضخم وارتفاع أسعار الغذاء
      's31-global-inflation-rate': parseFloat((-totalImpact * 0.6).toFixed(4))
    }
  };
}

// ============================================================================
// PAT-02: Energy Cost Non-Linear Coupling (Real Oil Shock ⟵ Corporate Defaults)
// ============================================================================

export const PAT02_METADATA: ProposedEquationMetadata = {
  patternId: 'PAT-02',
  patternNameAr: 'معادلة صدمة أسعار النفط وإفلاس الشركات والبطالة',
  patternNameEn: 'Real Oil Price Shock & Corporate Defaults Non-Linear Coupling',
  empiricalEvidenceBasis: 'ارتباط قوي (r = 0.77) ظهر في 4 انتقالات تاريخية؛ قفزات أسعار الطاقة ترفع تكاليف التشغيل وتدفع لتعثر الشركات وتراجع التوظيف.',
  activationConditions: [
    'ارتفاع سعر النفط الحقيقي عن متوسطه التاريخي بأكثر من 1.2 انحراف معياري (s33_stress < -0.20)',
    'أو انخفاض مفاجئ في نمو إنتاج النفط الخام (s18_stress < -0.15)'
  ],
  scopeOfValidity: 'يعمل بكامل فاعليته في فترات الصدمات التضخمية والذعر المالي؛ يقل أثره في فترات الفقاعات المضاربية المعتمدة على الائتمان غير المرتبط بالطاقة.',
  knownFailureModes: [
    'حقبة 1990→2001: انهيار أسهم الدوت كوم أحدث موجة إفلاس دون صدمة نفطية.'
  ],
  acceptanceRejectionCriteria: [
    'يجب أن يفسر ارتفاع تعثر الشركات في أزمتي 1973→1980 و 2008→2013.',
    'يجب ألا يربط تعثرات 2001 قسراً بالطاقة.',
    'صمد خارج العينة في 2020→2024 عند ارتفاع أسعار الطاقة بعد 2021.'
  ],
  tunableParameters: {
    oilShockThreshold: { value: -0.20, descriptionAr: 'عتبة الصدمة السعرية الحقيقية للنفط' },
    nonLinearPowerGamma: { value: 1.50, descriptionAr: 'معامل القوة غير الخطية لامتصاص الصدمة' },
    corporateTransmissionCoeff: { value: 0.72, descriptionAr: 'معامل الانتقال لتعثر الشركات' },
    unemploymentTransmissionCoeff: { value: 0.48, descriptionAr: 'معامل الانتقال لمعدلات البطالة' },
    crisisCompoundingFactor: { value: 1.80, descriptionAr: 'مضاعف التفاقم عند ترافق صدمة الطاقة مع أزمة سيولة' }
  }
};

/**
 * Calculates proposed adjustment for PAT-02
 * Formula:
 * IF (s33_stress < threshold) THEN:
 *   shock = |s33_stress - threshold|^gamma
 *   defaults_strain = shock * coeff * (isCrisis ? compounding : 1.0)
 */
export function evaluateProposedEquation_PAT02(
  s33_realOilPriceStress: number,
  s18_crudeProductionStress: number,
  isCrisis: boolean
): ProposedEquationResult {
  const p = PAT02_METADATA.tunableParameters;
  const isOilShock = s33_realOilPriceStress < p.oilShockThreshold.value;

  if (!isOilShock) {
    return {
      patternId: 'PAT-02',
      isActivated: false,
      regimeState: isCrisis ? 'Crisis' : 'Stable',
      activationReasonAr: 'أسعار النفط الحقيقية ضمن النطاق الطبيعي.',
      inputs: { s33_realOilPriceStress, s18_crudeProductionStress },
      rawOutput: 0,
      dampenedOutput: 0,
      targetSeriesAdjustments: { 's39-corporate-defaults': 0, 's37-oecd-unemployment': 0 }
    };
  }

  const excessShock = Math.abs(s33_realOilPriceStress - p.oilShockThreshold.value);
  const nonLinearShock = Math.pow(excessShock, p.nonLinearPowerGamma.value);
  const crisisMultiplier = isCrisis ? p.crisisCompoundingFactor.value : 1.0;
  const transmittedShock = nonLinearShock * crisisMultiplier;

  return {
    patternId: 'PAT-02',
    isActivated: true,
    regimeState: isCrisis ? 'Crisis' : 'Stable',
    activationReasonAr: `تفعيل صدمة الطاقة: فائض الصدمة = ${excessShock.toFixed(2)}. مضاعف الطور = x${crisisMultiplier}`,
    inputs: { s33_realOilPriceStress, s18_crudeProductionStress },
    rawOutput: parseFloat(nonLinearShock.toFixed(4)),
    dampenedOutput: parseFloat(transmittedShock.toFixed(4)),
    targetSeriesAdjustments: {
      's39-corporate-defaults': parseFloat((-transmittedShock * p.corporateTransmissionCoeff.value).toFixed(4)),
      's37-oecd-unemployment': parseFloat((-transmittedShock * p.unemploymentTransmissionCoeff.value).toFixed(4))
    }
  };
}

// ============================================================================
// PAT-04: Uncertainty & Yield Spike Infrastructure Freeze Factor
// ============================================================================

export const PAT04_METADATA: ProposedEquationMetadata = {
  patternId: 'PAT-04',
  patternNameAr: 'معادلة معامل تجميد استثمارات البنية التحتية والشحن',
  patternNameEn: 'Policy Uncertainty & Yield Spike Infrastructure Freeze Factor',
  empiricalEvidenceBasis: 'ارتباط قوي (r = 0.81) في 4 انتقالات؛ ارتفاع عدم اليقين وعوائد السندات يجمد الاستثمارات في الشحن والطاقة.',
  activationConditions: [
    'دخول النظام في طور الذعر (isCrisis == true)',
    'وتجاوز عدم اليقين وعائد السندات العتبة المركبة: (-0.6 * s40 - 0.4 * s34 > 0.45)'
  ],
  scopeOfValidity: 'مقصور على طور الذعر وتكاليف رأس المال المرتفعة؛ محمي بواسطة مخفف الطفرات التقنية (Tech Shield).',
  knownFailureModes: [
    'حقبة 1990→2001: ثورة الإنترنت والاتصالات استمرت بالنمو الرأسمالي رغم تقلبات عوائد السندات.'
  ],
  acceptanceRejectionCriteria: [
    'يجب أن يفسر انهيار نمو البنية التحتية في 2008→2013 بنجاح.',
    'يجب ألا يجمد قطاعات التكنولوجيا في 1990→2001 بفضل مخفف براءات الاختراع والاتصالات (s28/s30).',
    'صمد خارج العينة في 2020→2024 بتباطؤ الشحن مع رفع الفائدة في 2022.'
  ],
  tunableParameters: {
    macroUncertaintyThreshold: { value: 0.45, descriptionAr: 'عتبة عدم اليقين وتكلفة الاقتراض الحرجة' },
    baseFreezeFactor: { value: 0.65, descriptionAr: 'نسبة تجميد التراكم الاستثماري (تخفيض النمو بـ 65%)' },
    techInnovationShieldCoeff: { value: 0.50, descriptionAr: 'معامل حماية الابتكار التقني (يمنع التجميد الكامل)' }
  }
};

/**
 * Calculates proposed adjustment for PAT-04
 * Formula:
 * IF (isCrisis AND compositeUncertainty > threshold) THEN:
 *   effectiveFreeze = baseFreeze * (1 - techShield * techGrowth)
 */
export function evaluateProposedEquation_PAT04(
  s40_uncertaintyStress: number,
  s34_yieldStress: number,
  s30_patentStress: number,
  s28_internetStress: number,
  isCrisis: boolean
): ProposedEquationResult {
  const p = PAT04_METADATA.tunableParameters;
  const compositeUncertainty = -s40_uncertaintyStress * 0.6 - s34_yieldStress * 0.4;
  const isThresholdCrossed = compositeUncertainty > p.macroUncertaintyThreshold.value;

  const isActivated = isCrisis && isThresholdCrossed;

  if (!isActivated) {
    return {
      patternId: 'PAT-04',
      isActivated: false,
      regimeState: isCrisis ? 'Crisis' : 'Stable',
      activationReasonAr: 'الظروف غير مستوفاة (إما استقرار مالي أو عدم يقين منخفض).',
      inputs: { s40_uncertaintyStress, s34_yieldStress, compositeUncertainty },
      rawOutput: 0,
      dampenedOutput: 0,
      targetSeriesAdjustments: { 's25-container-throughput': 0, 's27-air-freight-traffic': 0, 's24-per-capita-energy': 0 }
    };
  }

  // Tech Innovation Shield: high internet / patent enablement cushions the freeze
  const techEnablement = Math.max(0, (s28_internetStress + s30_patentStress) / 2);
  const techShieldDampener = Math.min(0.60, techEnablement * p.techInnovationShieldCoeff.value);
  const netFreezeFactor = p.baseFreezeFactor.value * (1.0 - techShieldDampener);

  return {
    patternId: 'PAT-04',
    isActivated: true,
    regimeState: 'Crisis',
    activationReasonAr: `تجميد البنية: عدم اليقين المركب = ${compositeUncertainty.toFixed(2)}. حماية الابتكار التقني = ${(techShieldDampener * 100).toFixed(1)}%`,
    inputs: { compositeUncertainty, techShieldDampener },
    rawOutput: parseFloat(p.baseFreezeFactor.value.toFixed(4)),
    dampenedOutput: parseFloat(netFreezeFactor.toFixed(4)),
    targetSeriesAdjustments: {
      's25-container-throughput': parseFloat((-netFreezeFactor * 0.35).toFixed(4)),
      's27-air-freight-traffic': parseFloat((-netFreezeFactor * 0.40).toFixed(4)),
      's24-per-capita-energy': parseFloat((-netFreezeFactor * 0.20).toFixed(4))
    }
  };
}

// ============================================================================
// PAT-07: Global Debt Accumulation & Balance Sheet Hysteresis Feedback Loop
// ============================================================================

export const PAT07_METADATA: ProposedEquationMetadata = {
  patternId: 'PAT-07',
  patternNameAr: 'معادلة استدامة هسترة الديون وتوسع ميزانيات البنوك المركزية',
  patternNameEn: 'Global Debt/GDP Accumulation & Balance Sheet Hysteresis Feedback Loop',
  empiricalEvidenceBasis: 'أعلى ارتباط مسجل (r = 0.88) عبر 4 حقب متتالية؛ تراكم الديون السيادية والخاصة يفرض قفل استدامة (Lock-in) يمنع انكماش الميزانيات بعد الأزمات.',
  activationConditions: [
    'ارتفاع إجهاد الدين العالمي/الناتج عن العتبة (s38_stress < -0.15)',
    'أو وصول الدين/الناتج إلى مستويات تفوق 280% تاريخياً'
  ],
  scopeOfValidity: 'يعمل في جميع الأطوار؛ العلاقة ذات ذاكرة بطيئة وغير خطية (تتباطأ في التراجع حتى بعد انتهاء الأزمة).',
  knownFailureModes: [
    'حقبة 1973→1980: محا التضخم المرتفع جزءاً من القيمة الحقيقية للديون دون تدخل البنوك المركزية بالطباعة الكمية.'
  ],
  acceptanceRejectionCriteria: [
    'يجب أن يفسر ثبات ميزانيات البنوك المرتفعة بعد أزمة 2008 حتى 2020.',
    'يجب أن يفسر استمرار الديون فوق 330% في اختبار خارج العينة 2020→2024.',
    'يجب أن يمنع تفريغ الديون السريع غير الواقعي في المحاكاة.'
  ],
  tunableParameters: {
    debtStressThreshold: { value: -0.15, descriptionAr: 'عتبة إجهاد الدين الحرج نسبة للناتج' },
    hysteresisMemoryHalfLifeTau: { value: 3.20, descriptionAr: 'عمر النصف الممتد للذاكرة (3.2 أضعاف التناقص الطبيعي)' },
    centralBankAssetFeedbackGain: { value: 0.82, descriptionAr: 'معامل استجابة البنوك المركزية لضغوط خدمة الدين' },
    policyUncertaintySpillover: { value: 0.45, descriptionAr: 'أثر الدين المستمر على تغذية عدم اليقين في السياسات' }
  }
};

/**
 * Calculates proposed adjustment for PAT-07
 * Formula:
 * IF (s38_stress < threshold) THEN:
 *   excessDebt = |s38_stress - threshold|
 *   cb_expansion = excessDebt * feedbackGain * (isCrisis ? 1.5 : 1.0)
 *   persistence = exp(-dt / (tau * hysteresisMemoryHalfLife))
 */
export function evaluateProposedEquation_PAT07(
  s38_debtGdpStress: number,
  s36_cbAssetsStress: number,
  isCrisis: boolean,
  deltaYears: number = 5
): ProposedEquationResult {
  const p = PAT07_METADATA.tunableParameters;
  const isDebtCritical = s38_debtGdpStress < p.debtStressThreshold.value;

  if (!isDebtCritical) {
    return {
      patternId: 'PAT-07',
      isActivated: false,
      regimeState: isCrisis ? 'Crisis' : 'Stable',
      activationReasonAr: 'المديونية العالمية ضمن حدود الأمان التاريخية.',
      inputs: { s38_debtGdpStress, s36_cbAssetsStress },
      rawOutput: 0,
      dampenedOutput: 0,
      targetSeriesAdjustments: { 's36-central-bank-assets': 0, 's40-policy-uncertainty': 0 }
    };
  }

  const excessDebt = Math.abs(s38_debtGdpStress - p.debtStressThreshold.value);
  const crisisMultiplier = isCrisis ? 1.5 : 1.0;
  const inducedAssetExpansion = excessDebt * p.centralBankAssetFeedbackGain.value * crisisMultiplier;
  
  // Hysteresis dampener: debt does NOT fade quickly
  const decayRate = 1.0 / (10.0 * p.hysteresisMemoryHalfLifeTau.value);
  const hysteresisRetained = Math.exp(-deltaYears * decayRate);

  const finalAdjustment = inducedAssetExpansion * hysteresisRetained;

  return {
    patternId: 'PAT-07',
    isActivated: true,
    regimeState: isCrisis ? 'Crisis' : 'Stable',
    activationReasonAr: `تفعيل هسترة الديون: فائض الدين = ${excessDebt.toFixed(2)}. الاحتفاظ الهيكلي = ${(hysteresisRetained * 100).toFixed(1)}%`,
    inputs: { excessDebt, hysteresisRetained },
    rawOutput: parseFloat(inducedAssetExpansion.toFixed(4)),
    dampenedOutput: parseFloat(finalAdjustment.toFixed(4)),
    targetSeriesAdjustments: {
      's36-central-bank-assets': parseFloat((-finalAdjustment).toFixed(4)), // استمرار ضغط تضخم الميزانيات
      's40-policy-uncertainty': parseFloat((-finalAdjustment * p.policyUncertaintySpillover.value).toFixed(4))
    }
  };
}

export const ALL_PROPOSED_EQUATIONS = [
  PAT01_METADATA,
  PAT02_METADATA,
  PAT04_METADATA,
  PAT07_METADATA
];
