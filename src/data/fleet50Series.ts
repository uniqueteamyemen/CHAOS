// src/data/fleet50Series.ts
// The Core 50 Baseline Fleet for Governed Human Impact Dynamics (1970 - 2024)
// Structured across three fundamental operational layers:
// 1. Nature / Exogenous (Omega): gamma ~ 0.0 - 0.15
// 2. Infrastructure / Mediating (Phi): gamma ~ 0.3 - 0.75
// 3. Human Decisions / Endogenous (Psi): gamma ~ 0.8 - 1.0

export interface FleetSeriesItem {
  id: string;
  nameAr: string;
  nameEn: string;
  layer: 'nature' | 'infrastructure' | 'human_system';
  source: string;
  unit: string;
  gamma: number; // Anthropogenic generation ratio [0, 1]
  defaultDurationYears: number; // Typical human temporal footprint (tau)
  descriptionAr: string;
  // Year 2008 reference snapshot
  snapshot2008: {
    rawValue: number;
    eventDescriptionAr: string;
    directSign: 1 | -1 | 0; // 1 = benefit/enablement, -1 = strain/disruption, 0 = neutral/unresolved
    observedDurationYears: number;
    humanCoverageRatio: number; // 0 to 1
  };
  // Multi-year trajectory points (selected benchmark milestones: 1973, 1980, 1990, 2001, 2008, 2020, 2024)
  benchmarks: {
    year: number;
    value: number;
    normalizedStress: number; // -1 (max human strain) to +1 (max enablement), 0 neutral
  }[];
}

export const FLEET_50_SERIES: FleetSeriesItem[] = [
  // ==========================================
  // LAYER 1: NATURE / EXOGENOUS (10 SERIES)
  // gamma ~ 0.0 - 0.15 (External forcing, human vulnerability test)
  // ==========================================
  {
    id: 's01-solar-cycle',
    nameAr: 'النشاط المغناطيسي الشمسي (عدد البقع الشمسية)',
    nameEn: 'International Sunspot Number (SILSO)',
    layer: 'nature',
    source: 'SILSO / Royal Observatory of Belgium',
    unit: 'Annual Mean Sunspot Number',
    gamma: 0.01,
    defaultDurationYears: 11.1,
    descriptionAr: 'الدورة المغناطيسية الشمسية المؤثرة على الغلاف الشمسي والأقمار الصناعية وشبكات الكهرباء الشمالية.',
    snapshot2008: {
      rawValue: 4.2,
      eventDescriptionAr: 'القاع العميق للدورة 23 - أدنى نشاط شمسي مسجل منذ قرن تقريباً.',
      directSign: 0,
      observedDurationYears: 11.0,
      humanCoverageRatio: 0.05
    },
    benchmarks: [
      { year: 1973, value: 54.0, normalizedStress: 0.0 },
      { year: 1980, value: 218.0, normalizedStress: -0.1 },
      { year: 1990, value: 200.0, normalizedStress: -0.1 },
      { year: 2001, value: 170.0, normalizedStress: -0.05 },
      { year: 2008, value: 4.2, normalizedStress: 0.0 },
      { year: 2020, value: 8.8, normalizedStress: 0.0 },
      { year: 2024, value: 155.0, normalizedStress: -0.1 }
    ]
  },
  {
    id: 's02-enso-nino34',
    nameAr: 'شذوذ حرارة المحيط الهادئ (مؤشر النينيو ENSO)',
    nameEn: 'ENSO Oceanic Nino Index (Nino 3.4 SST Anomaly)',
    layer: 'nature',
    source: 'NOAA Climate Prediction Center',
    unit: '°C Anomaly',
    gamma: 0.08,
    defaultDurationYears: 3.5,
    descriptionAr: 'تذبذب المحيط الهادئ الاستوائي الذي يقلب أنماط الجفاف والفيضانات على سلال الغذاء العالمية.',
    snapshot2008: {
      rawValue: -0.75,
      eventDescriptionAr: 'ظاهرة لانينا قوية سببت برودة نسبية في الباسيفيك وتغيرات مطرية إقليمية.',
      directSign: 0,
      observedDurationYears: 2.0,
      humanCoverageRatio: 0.25
    },
    benchmarks: [
      { year: 1973, value: -1.2, normalizedStress: -0.2 },
      { year: 1980, value: 0.4, normalizedStress: 0.0 },
      { year: 1990, value: 0.4, normalizedStress: 0.0 },
      { year: 2001, value: -0.3, normalizedStress: 0.0 },
      { year: 2008, value: -0.75, normalizedStress: -0.1 },
      { year: 2020, value: -0.9, normalizedStress: -0.1 },
      { year: 2024, value: 0.8, normalizedStress: -0.2 }
    ]
  },
  {
    id: 's03-nao-index',
    nameAr: 'تذبذب شمال الأطلسي (NAO)',
    nameEn: 'North Atlantic Oscillation Index',
    layer: 'nature',
    source: 'NOAA CPC / NCAR',
    unit: 'Normalized Pressure Anomaly Index',
    gamma: 0.03,
    defaultDurationYears: 2.5,
    descriptionAr: 'فرق الضغط الجوي المؤثر على شتاء أوروبا وشمال إفريقيا وموارد المياه العذبة.',
    snapshot2008: {
      rawValue: 0.35,
      eventDescriptionAr: 'طور إيجابي معتدل حافظ على مسارات العواصف الأطلسية القياسية.',
      directSign: 0,
      observedDurationYears: 1.5,
      humanCoverageRatio: 0.15
    },
    benchmarks: [
      { year: 1973, value: 0.5, normalizedStress: 0.0 },
      { year: 1980, value: 0.2, normalizedStress: 0.0 },
      { year: 1990, value: 1.2, normalizedStress: 0.1 },
      { year: 2001, value: -0.2, normalizedStress: 0.0 },
      { year: 2008, value: 0.35, normalizedStress: 0.0 },
      { year: 2020, value: 0.6, normalizedStress: 0.0 },
      { year: 2024, value: 0.2, normalizedStress: 0.0 }
    ]
  },
  {
    id: 's04-global-seismic-energy',
    nameAr: 'الطاقة الزلزالية الكبرى المحررة (M≥6.5)',
    nameEn: 'Global Major Earthquakes Energy Release (USGS)',
    layer: 'nature',
    source: 'USGS National Earthquake Information Center',
    unit: '10^17 Joules equivalent',
    gamma: 0.02,
    defaultDurationYears: 2.0,
    descriptionAr: 'تفريغ طاقة الصفائح التكتونية في البؤر المأهولة وغير المأهولة.',
    snapshot2008: {
      rawValue: 18.5,
      eventDescriptionAr: 'زلزال سيشوان المدمر M7.9 في الصين وزلازل سومطرة الإقليمية.',
      directSign: -1,
      observedDurationYears: 4.0,
      humanCoverageRatio: 0.12
    },
    benchmarks: [
      { year: 1973, value: 12.0, normalizedStress: -0.1 },
      { year: 1980, value: 10.5, normalizedStress: -0.1 },
      { year: 1990, value: 14.2, normalizedStress: -0.2 },
      { year: 2001, value: 16.0, normalizedStress: -0.2 },
      { year: 2008, value: 24.5, normalizedStress: -0.5 },
      { year: 2020, value: 9.8, normalizedStress: -0.1 },
      { year: 2024, value: 13.5, normalizedStress: -0.2 }
    ]
  },
  {
    id: 's05-global-temp-anomaly',
    nameAr: 'شذوذ حرارة سطح الأرض والمحيطات العالمية',
    nameEn: 'Global Surface Temperature Anomaly (NASA GISTEMP)',
    layer: 'nature',
    source: 'NASA Goddard Institute for Space Studies',
    unit: '°C relative to 1951-1980',
    gamma: 0.35,
    defaultDurationYears: 20.0,
    descriptionAr: 'متوسط ارتفاع درجات الحرارة العالمية نتيجة مزيج الدورة الطبيعية والنشاط البشري المتراكم.',
    snapshot2008: {
      rawValue: 0.54,
      eventDescriptionAr: 'انخفاض طفيف عن 2007 بسبب لانينا، لكنه بقي ضمن أكثر 10 سنوات حرارة حتى حينه.',
      directSign: 0,
      observedDurationYears: 10.0,
      humanCoverageRatio: 0.50
    },
    benchmarks: [
      { year: 1973, value: 0.17, normalizedStress: 0.0 },
      { year: 1980, value: 0.26, normalizedStress: -0.05 },
      { year: 1990, value: 0.45, normalizedStress: -0.1 },
      { year: 2001, value: 0.54, normalizedStress: -0.15 },
      { year: 2008, value: 0.54, normalizedStress: -0.2 },
      { year: 2020, value: 1.02, normalizedStress: -0.4 },
      { year: 2024, value: 1.25, normalizedStress: -0.6 }
    ]
  },
  {
    id: 's06-global-precipitation',
    nameAr: 'معدل هطول الأمطار العالمي فوق اليابسة',
    nameEn: 'Global Terrestrial Precipitation Anomaly (GPCC)',
    layer: 'nature',
    source: 'Global Precipitation Climatology Centre (DWD/WMO)',
    unit: 'mm anomaly',
    gamma: 0.15,
    defaultDurationYears: 3.0,
    descriptionAr: 'دورة الهطول المائي المغذية للأحواض المائية الجوفية والمحاصيل البعلية.',
    snapshot2008: {
      rawValue: 12.0,
      eventDescriptionAr: 'معدل هطول أعلى من المتوسط عالمياً عزز إنتاج الحبوب وأحواض السدود.',
      directSign: 1,
      observedDurationYears: 1.5,
      humanCoverageRatio: 0.40
    },
    benchmarks: [
      { year: 1973, value: 25.0, normalizedStress: 0.2 },
      { year: 1980, value: -5.0, normalizedStress: 0.0 },
      { year: 1990, value: -12.0, normalizedStress: -0.1 },
      { year: 2001, value: 5.0, normalizedStress: 0.0 },
      { year: 2008, value: 12.0, normalizedStress: 0.2 },
      { year: 2020, value: 18.0, normalizedStress: 0.1 },
      { year: 2024, value: -2.0, normalizedStress: 0.0 }
    ]
  },
  {
    id: 's07-arctic-ice-extent',
    nameAr: 'امتداد الجليد البحري في القطب الشمالي',
    nameEn: 'Arctic Sea Ice Minimum Extent',
    layer: 'nature',
    source: 'National Snow and Ice Data Center (NSIDC)',
    unit: 'Million km²',
    gamma: 0.30,
    defaultDurationYears: 15.0,
    descriptionAr: 'مرآة الانعكاس الإشعاعي لكوكب الأرض ومؤشر اتزان التيارات القطبية.',
    snapshot2008: {
      rawValue: 4.69,
      eventDescriptionAr: 'ثاني أدنى مستوى قياسي مسجل بعد انهيار 2007 المفاجئ.',
      directSign: 0,
      observedDurationYears: 8.0,
      humanCoverageRatio: 0.10
    },
    benchmarks: [
      { year: 1973, value: 7.8, normalizedStress: 0.0 },
      { year: 1980, value: 7.5, normalizedStress: 0.0 },
      { year: 1990, value: 6.2, normalizedStress: -0.05 },
      { year: 2001, value: 6.7, normalizedStress: -0.1 },
      { year: 2008, value: 4.69, normalizedStress: -0.2 },
      { year: 2020, value: 3.82, normalizedStress: -0.4 },
      { year: 2024, value: 4.28, normalizedStress: -0.35 }
    ]
  },
  {
    id: 's08-sea-level-rise',
    nameAr: 'مستوى سطح البحر العالمي النسبي',
    nameEn: 'Global Mean Sea Level Change (NASA/CSIRO)',
    layer: 'nature',
    source: 'NASA Sea Level Change Portal / CSIRO',
    unit: 'mm above 1993 baseline',
    gamma: 0.40,
    defaultDurationYears: 30.0,
    descriptionAr: 'تمدد مياه المحيطات الحراري وذوبان الصفائح الجليدية الضاغط على الدلتاوات والمدن الساحلية.',
    snapshot2008: {
      rawValue: 42.1,
      eventDescriptionAr: 'ارتفاع تدريجي متواصل بمعدل 3.1 مم سنوياً دون تسارع انقطاعي مفاجئ.',
      directSign: 0,
      observedDurationYears: 15.0,
      humanCoverageRatio: 0.20
    },
    benchmarks: [
      { year: 1973, value: -25.0, normalizedStress: 0.0 },
      { year: 1980, value: -12.0, normalizedStress: 0.0 },
      { year: 1990, value: 3.0, normalizedStress: -0.05 },
      { year: 2001, value: 24.0, normalizedStress: -0.1 },
      { year: 2008, value: 42.1, normalizedStress: -0.15 },
      { year: 2020, value: 89.5, normalizedStress: -0.3 },
      { year: 2024, value: 104.2, normalizedStress: -0.4 }
    ]
  },
  {
    id: 's09-volcanic-stratospheric-aod',
    nameAr: 'الضباب البركاني في الستراتوسفير (حجب الضوء)',
    nameEn: 'Stratospheric Volcanic Aerosol Optical Depth (NASA GISS)',
    layer: 'nature',
    source: 'NASA GISS Sato Index',
    unit: 'Optical Depth (unitless)',
    gamma: 0.0,
    defaultDurationYears: 3.0,
    descriptionAr: 'حقن الغازات الكبريتية في طبقة الستراتوسفير القادر على تبريد الأرض وتعطيل الصيف الزراعي.',
    snapshot2008: {
      rawValue: 0.003,
      eventDescriptionAr: 'فترة هدوء بركاني شبه تام، ونفاذية شمسية عالية جداً.',
      directSign: 1,
      observedDurationYears: 1.0,
      humanCoverageRatio: 0.70
    },
    benchmarks: [
      { year: 1973, value: 0.004, normalizedStress: 0.0 },
      { year: 1980, value: 0.012, normalizedStress: -0.1 },
      { year: 1990, value: 0.006, normalizedStress: 0.0 },
      { year: 2001, value: 0.002, normalizedStress: 0.0 },
      { year: 2008, value: 0.003, normalizedStress: 0.05 },
      { year: 2020, value: 0.005, normalizedStress: 0.0 },
      { year: 2024, value: 0.004, normalizedStress: 0.0 }
    ]
  },
  {
    id: 's10-cosmic-rays',
    nameAr: 'تدفق الأشعة الكونية المجرية (Oulu Neutron Monitor)',
    nameEn: 'Galactic Cosmic Ray Flux (Oulu Station)',
    layer: 'nature',
    source: 'University of Oulu Sodankyla Geophysical Observatory',
    unit: 'Counts / minute',
    gamma: 0.0,
    defaultDurationYears: 11.0,
    descriptionAr: 'جسيمات الطاقة العالية من خارج المجموعة الشمسية، تبلغ ذروتها عند قيعان الدورة الشمسية.',
    snapshot2008: {
      rawValue: 6720,
      eventDescriptionAr: 'ذروة تدفق كوني تاريخية نتيجة ضعف الرياح الشمسية الواقية.',
      directSign: 0,
      observedDurationYears: 4.0,
      humanCoverageRatio: 0.02
    },
    benchmarks: [
      { year: 1973, value: 6100, normalizedStress: 0.0 },
      { year: 1980, value: 5200, normalizedStress: 0.0 },
      { year: 1990, value: 5350, normalizedStress: 0.0 },
      { year: 2001, value: 5400, normalizedStress: 0.0 },
      { year: 2008, value: 6720, normalizedStress: 0.0 },
      { year: 2020, value: 6650, normalizedStress: 0.0 },
      { year: 2024, value: 5600, normalizedStress: 0.0 }
    ]
  },

  // ==========================================
  // LAYER 2: INFRASTRUCTURE & MEDIATION (20 SERIES)
  // gamma ~ 0.3 - 0.75 (Buffering and human adaptation shield)
  // ==========================================
  {
    id: 's11-wheat-production',
    nameAr: 'إنتاج القمح العالمي السنوي',
    nameEn: 'Global Wheat Production (FAOSTAT)',
    layer: 'infrastructure',
    source: 'FAOSTAT / USDA FAS',
    unit: 'Million Metric Tons',
    gamma: 0.70,
    defaultDurationYears: 3.0,
    descriptionAr: 'محصول الخبز الأساسي لنصف سكان العالم ومحدد كفاءة صمود الأمن الغذائي.',
    snapshot2008: {
      rawValue: 683.0,
      eventDescriptionAr: 'محصول قمح قياسي تاريخي (+11.8% نمو) أسهم في كسر شبح المجاعة الحادة.',
      directSign: 1,
      observedDurationYears: 4.0,
      humanCoverageRatio: 0.85
    },
    benchmarks: [
      { year: 1973, value: 377.0, normalizedStress: 0.1 },
      { year: 1980, value: 440.0, normalizedStress: 0.1 },
      { year: 1990, value: 588.0, normalizedStress: 0.3 },
      { year: 2001, value: 589.0, normalizedStress: 0.2 },
      { year: 2008, value: 683.0, normalizedStress: 0.6 },
      { year: 2020, value: 760.0, normalizedStress: 0.7 },
      { year: 2024, value: 795.0, normalizedStress: 0.8 }
    ]
  },
  {
    id: 's12-rice-production',
    nameAr: 'إنتاج الأرز المطحون العالمي',
    nameEn: 'Global Milled Rice Production (FAOSTAT)',
    layer: 'infrastructure',
    source: 'FAOSTAT / IRRI',
    unit: 'Million Metric Tons',
    gamma: 0.75,
    defaultDurationYears: 2.5,
    descriptionAr: 'السعرات الحرارية الأساسية لآسيا وأحواض الأنهار المكتظة سكانياً.',
    snapshot2008: {
      rawValue: 448.0,
      eventDescriptionAr: 'وفرة محصولية قياسية رغم حظر التصدير المؤقت الذي فرضته بعض الحكومات.',
      directSign: 1,
      observedDurationYears: 3.0,
      humanCoverageRatio: 0.75
    },
    benchmarks: [
      { year: 1973, value: 212.0, normalizedStress: 0.1 },
      { year: 1980, value: 269.0, normalizedStress: 0.2 },
      { year: 1990, value: 351.0, normalizedStress: 0.3 },
      { year: 2001, value: 399.0, normalizedStress: 0.35 },
      { year: 2008, value: 448.0, normalizedStress: 0.5 },
      { year: 2020, value: 508.0, normalizedStress: 0.7 },
      { year: 2024, value: 530.0, normalizedStress: 0.75 }
    ]
  },
  {
    id: 's13-corn-production',
    nameAr: 'إنتاج الذرة العالمي',
    nameEn: 'Global Maize/Corn Production (FAOSTAT)',
    layer: 'infrastructure',
    source: 'FAOSTAT / USDA',
    unit: 'Million Metric Tons',
    gamma: 0.72,
    defaultDurationYears: 2.5,
    descriptionAr: 'عماد صناعة الأعلاف والوقود الحيوي والنشا الصناعي.',
    snapshot2008: {
      rawValue: 827.0,
      eventDescriptionAr: 'قفزة إنتاجية كبرى استوعبت طلب الإيثانول ومنعت عجز الأعلاف الحيوانية.',
      directSign: 1,
      observedDurationYears: 3.0,
      humanCoverageRatio: 0.65
    },
    benchmarks: [
      { year: 1973, value: 312.0, normalizedStress: 0.1 },
      { year: 1980, value: 396.0, normalizedStress: 0.2 },
      { year: 1990, value: 483.0, normalizedStress: 0.3 },
      { year: 2001, value: 615.0, normalizedStress: 0.4 },
      { year: 2008, value: 827.0, normalizedStress: 0.6 },
      { year: 2020, value: 1162.0, normalizedStress: 0.75 },
      { year: 2024, value: 1225.0, normalizedStress: 0.8 }
    ]
  },
  {
    id: 's14-soybean-production',
    nameAr: 'إنتاج فول الصويا العالمي',
    nameEn: 'Global Soybean Production (FAOSTAT)',
    layer: 'infrastructure',
    source: 'FAOSTAT / USDA',
    unit: 'Million Metric Tons',
    gamma: 0.75,
    defaultDurationYears: 2.0,
    descriptionAr: 'المصدر الأكبر للبروتين النباتي وزيت الطعام وعلف الدواجن والماشية.',
    snapshot2008: {
      rawValue: 231.0,
      eventDescriptionAr: 'استقرار في معروض البروتين العالمي رغم جفاف الأرجنتين في ذلك الموسم.',
      directSign: 1,
      observedDurationYears: 2.0,
      humanCoverageRatio: 0.60
    },
    benchmarks: [
      { year: 1973, value: 56.0, normalizedStress: 0.05 },
      { year: 1980, value: 81.0, normalizedStress: 0.1 },
      { year: 1990, value: 108.0, normalizedStress: 0.2 },
      { year: 2001, value: 184.0, normalizedStress: 0.35 },
      { year: 2008, value: 231.0, normalizedStress: 0.45 },
      { year: 2020, value: 353.0, normalizedStress: 0.65 },
      { year: 2024, value: 398.0, normalizedStress: 0.7 }
    ]
  },
  {
    id: 's15-grain-stocks-to-use',
    nameAr: 'مؤشر مخزون الحبوب العالمي إلى الاستهلاك',
    nameEn: 'Global Grain Stocks-to-Use Ratio (AMIS/FAO)',
    layer: 'infrastructure',
    source: 'FAO AMIS / USDA PSD',
    unit: 'Percentage (%)',
    gamma: 0.80,
    defaultDurationYears: 3.0,
    descriptionAr: 'صمام الأمان الحقيقي لمنع المجاعات؛ انخفاضه يعني خطراً فادحاً عند أي تقلب مناخي.',
    snapshot2008: {
      rawValue: 19.8,
      eventDescriptionAr: 'قاع خطير ومقلق اقترب من مستويات أزمة السبعينيات قبل أن يبدأ التعافي في نهاية العام.',
      directSign: -1,
      observedDurationYears: 3.0,
      humanCoverageRatio: 0.80
    },
    benchmarks: [
      { year: 1973, value: 15.2, normalizedStress: -0.7 },
      { year: 1980, value: 22.0, normalizedStress: -0.2 },
      { year: 1990, value: 27.5, normalizedStress: 0.3 },
      { year: 2001, value: 30.1, normalizedStress: 0.4 },
      { year: 2008, value: 19.8, normalizedStress: -0.4 },
      { year: 2020, value: 29.5, normalizedStress: 0.3 },
      { year: 2024, value: 28.2, normalizedStress: 0.25 }
    ]
  },
  {
    id: 's16-meat-production',
    nameAr: 'إنتاج اللحوم الإجمالي عالمياً',
    nameEn: 'Total World Meat Production (FAOSTAT)',
    layer: 'infrastructure',
    source: 'FAOSTAT',
    unit: 'Million Metric Tons',
    gamma: 0.85,
    defaultDurationYears: 3.0,
    descriptionAr: 'مستوى استهلاك البروتين الحيواني المرتبط بالرفاه الاقتصادي واتساع الطبقة الوسطى.',
    snapshot2008: {
      rawValue: 284.0,
      eventDescriptionAr: 'استمرار الصعود المستقر لإنتاج الدواجن واللحوم عالمياً رغم ارتفاع تكاليف العلف.',
      directSign: 1,
      observedDurationYears: 4.0,
      humanCoverageRatio: 0.70
    },
    benchmarks: [
      { year: 1973, value: 108.0, normalizedStress: 0.1 },
      { year: 1980, value: 136.0, normalizedStress: 0.2 },
      { year: 1990, value: 180.0, normalizedStress: 0.3 },
      { year: 2001, value: 237.0, normalizedStress: 0.4 },
      { year: 2008, value: 284.0, normalizedStress: 0.55 },
      { year: 2020, value: 337.0, normalizedStress: 0.65 },
      { year: 2024, value: 365.0, normalizedStress: 0.7 }
    ]
  },
  {
    id: 's17-nitrogen-fertilizer',
    nameAr: 'إنتاج الأسمدة النيتروجينية الزراعية',
    nameEn: 'Global Nitrogen Fertilizer Consumption (IFA/FAO)',
    layer: 'infrastructure',
    source: 'International Fertilizer Association / FAO',
    unit: 'Million Tons of Nutrient N',
    gamma: 0.90,
    defaultDurationYears: 2.0,
    descriptionAr: 'الوقود الكيميائي للثورة الخضراء الذي يطعم نصف البشرية عبر تفاعل هابر-بوش.',
    snapshot2008: {
      rawValue: 102.0,
      eventDescriptionAr: 'ارتفاع حاد في تكلفة الإنتاج لارتباطها بسعر الغاز الطبيعي والنفط.',
      directSign: -1,
      observedDurationYears: 2.0,
      humanCoverageRatio: 0.80
    },
    benchmarks: [
      { year: 1973, value: 38.0, normalizedStress: 0.1 },
      { year: 1980, value: 60.0, normalizedStress: 0.2 },
      { year: 1990, value: 77.0, normalizedStress: 0.3 },
      { year: 2001, value: 84.0, normalizedStress: 0.35 },
      { year: 2008, value: 102.0, normalizedStress: -0.2 },
      { year: 2020, value: 111.0, normalizedStress: 0.4 },
      { year: 2024, value: 118.0, normalizedStress: 0.45 }
    ]
  },
  {
    id: 's18-crude-oil-production',
    nameAr: 'إنتاج النفط الخام والمكثفات العالمي',
    nameEn: 'Global Crude Oil Production (Energy Institute / EIA)',
    layer: 'infrastructure',
    source: 'Energy Institute Statistical Review / US EIA',
    unit: 'Million Barrels / Day',
    gamma: 0.90,
    defaultDurationYears: 5.0,
    descriptionAr: 'شريان الطاقة الأساسي الذي يُشغل النقل والزراعة والصناعات البتروكيماوية.',
    snapshot2008: {
      rawValue: 82.5,
      eventDescriptionAr: 'جمود نسبي في الطاقة الإنتاجية الفائضة ما فجر الأسعار لقمة 147$ قبل انهيار الطلب.',
      directSign: -1,
      observedDurationYears: 4.0,
      humanCoverageRatio: 0.90
    },
    benchmarks: [
      { year: 1973, value: 55.7, normalizedStress: -0.4 },
      { year: 1980, value: 62.8, normalizedStress: -0.3 },
      { year: 1990, value: 65.5, normalizedStress: 0.1 },
      { year: 2001, value: 74.8, normalizedStress: 0.2 },
      { year: 2008, value: 82.5, normalizedStress: -0.4 },
      { year: 2020, value: 88.4, normalizedStress: -0.2 },
      { year: 2024, value: 96.5, normalizedStress: 0.3 }
    ]
  },
  {
    id: 's19-coal-consumption',
    nameAr: 'استهلاك الفحم الحجري العالمي',
    nameEn: 'Global Coal Consumption (Energy Institute)',
    layer: 'infrastructure',
    source: 'Energy Institute Statistical Review',
    unit: 'Exajoules (EJ)',
    gamma: 0.85,
    defaultDurationYears: 10.0,
    descriptionAr: 'المصدر الرخيص والأكثر كثافة كربونية لتوليد الكهرباء وصهر الحديد في الاقتصادات النامية.',
    snapshot2008: {
      rawValue: 139.0,
      eventDescriptionAr: 'نمو صاروخي مدفوعاً بالتصنيع الصيني، وفّر طاقة هائلة لكن زاد التلوث المتراكم.',
      directSign: -1,
      observedDurationYears: 10.0,
      humanCoverageRatio: 0.60
    },
    benchmarks: [
      { year: 1973, value: 65.0, normalizedStress: 0.1 },
      { year: 1980, value: 78.0, normalizedStress: 0.1 },
      { year: 1990, value: 92.0, normalizedStress: 0.0 },
      { year: 2001, value: 99.0, normalizedStress: 0.0 },
      { year: 2008, value: 139.0, normalizedStress: -0.2 },
      { year: 2020, value: 151.0, normalizedStress: -0.3 },
      { year: 2024, value: 164.0, normalizedStress: -0.35 }
    ]
  },
  {
    id: 's20-gas-consumption',
    nameAr: 'استهلاك الغاز الطبيعي العالمي',
    nameEn: 'Global Natural Gas Consumption (Energy Institute)',
    layer: 'infrastructure',
    source: 'Energy Institute / IEA',
    unit: 'Billion Cubic Meters (BCM)',
    gamma: 0.85,
    defaultDurationYears: 5.0,
    descriptionAr: 'الوقود الانتقالي للكهرباء النظيفة والتدفئة المنزلية والصناعات الثقيلة.',
    snapshot2008: {
      rawValue: 3015.0,
      eventDescriptionAr: 'توسع مستمر وتدفق مستقر عبر خطوط الأنابيب قبل ثورة الغاز الصخري.',
      directSign: 1,
      observedDurationYears: 5.0,
      humanCoverageRatio: 0.65
    },
    benchmarks: [
      { year: 1973, value: 1100.0, normalizedStress: 0.1 },
      { year: 1980, value: 1400.0, normalizedStress: 0.2 },
      { year: 1990, value: 1950.0, normalizedStress: 0.3 },
      { year: 2001, value: 2490.0, normalizedStress: 0.4 },
      { year: 2008, value: 3015.0, normalizedStress: 0.5 },
      { year: 2020, value: 3820.0, normalizedStress: 0.6 },
      { year: 2024, value: 4050.0, normalizedStress: 0.65 }
    ]
  },
  {
    id: 's21-hydro-generation',
    nameAr: 'توليد الطاقة الكهرومائية العالمي',
    nameEn: 'Global Hydroelectricity Generation',
    layer: 'infrastructure',
    source: 'Energy Institute / IEA',
    unit: 'Terawatt-hours (TWh)',
    gamma: 0.65,
    defaultDurationYears: 15.0,
    descriptionAr: 'أكبر مصدر متجدد للكهرباء الأساسية ومنظم الفيضانات وتخزين المياه العذبة.',
    snapshot2008: {
      rawValue: 3260.0,
      eventDescriptionAr: 'نمو مطرد بفضل مشروعات السدود الكبرى في آسيا وأمريكا اللاتينية.',
      directSign: 1,
      observedDurationYears: 10.0,
      humanCoverageRatio: 0.50
    },
    benchmarks: [
      { year: 1973, value: 1300.0, normalizedStress: 0.1 },
      { year: 1980, value: 1730.0, normalizedStress: 0.2 },
      { year: 1990, value: 2160.0, normalizedStress: 0.3 },
      { year: 2001, value: 2580.0, normalizedStress: 0.4 },
      { year: 2008, value: 3260.0, normalizedStress: 0.55 },
      { year: 2020, value: 4350.0, normalizedStress: 0.7 },
      { year: 2024, value: 4500.0, normalizedStress: 0.75 }
    ]
  },
  {
    id: 's22-nuclear-generation',
    nameAr: 'توليد الكهرباء النووية عالمياً',
    nameEn: 'Global Nuclear Power Generation (IAEA PRIS)',
    layer: 'infrastructure',
    source: 'IAEA Power Reactor Information System',
    unit: 'Terawatt-hours (TWh)',
    gamma: 0.95,
    defaultDurationYears: 20.0,
    descriptionAr: 'طاقة الحمل الأساسي الخالية من الكربون وعالية الكثافة الطاقية.',
    snapshot2008: {
      rawValue: 2600.0,
      eventDescriptionAr: 'تراجع طفيف بنسبة 2% مقارنة بـ 2006 نتيجة إغلاق بعض المفاعلات القديمة في أوروبا واليابان.',
      directSign: -1,
      observedDurationYears: 5.0,
      humanCoverageRatio: 0.40
    },
    benchmarks: [
      { year: 1973, value: 200.0, normalizedStress: 0.05 },
      { year: 1980, value: 680.0, normalizedStress: 0.2 },
      { year: 1990, value: 1900.0, normalizedStress: 0.5 },
      { year: 2001, value: 2540.0, normalizedStress: 0.6 },
      { year: 2008, value: 2600.0, normalizedStress: 0.4 },
      { year: 2020, value: 2550.0, normalizedStress: 0.35 },
      { year: 2024, value: 2680.0, normalizedStress: 0.4 }
    ]
  },
  {
    id: 's23-electricity-access',
    nameAr: 'نسبة سكان العالم الحاصلين على الكهرباء',
    nameEn: 'Access to Electricity (% of World Population)',
    layer: 'infrastructure',
    source: 'World Bank WDI / IEA / WHO',
    unit: 'Percentage (%)',
    gamma: 0.95,
    defaultDurationYears: 25.0,
    descriptionAr: 'المقياس المباشر لانتشال الإنسان من فقر الطاقة وتمكينه من التبريد والتعليم والصحة.',
    snapshot2008: {
      rawValue: 80.2,
      eventDescriptionAr: 'عبور عتبة 80% عالمياً، وإيصال الكهرباء لعشرات الملايين سنوياً في الهند والريف الآسيوي.',
      directSign: 1,
      observedDurationYears: 20.0,
      humanCoverageRatio: 0.80
    },
    benchmarks: [
      { year: 1973, value: 58.0, normalizedStress: -0.4 },
      { year: 1980, value: 65.0, normalizedStress: -0.2 },
      { year: 1990, value: 71.4, normalizedStress: 0.0 },
      { year: 2001, value: 76.5, normalizedStress: 0.3 },
      { year: 2008, value: 80.2, normalizedStress: 0.5 },
      { year: 2020, value: 90.5, normalizedStress: 0.8 },
      { year: 2024, value: 91.8, normalizedStress: 0.85 }
    ]
  },
  {
    id: 's24-per-capita-energy',
    nameAr: 'استهلاك الطاقة الأولية للفرد عالمياً',
    nameEn: 'Primary Energy Consumption Per Capita (Energy Institute)',
    layer: 'infrastructure',
    source: 'Energy Institute / World Bank',
    unit: 'Gigajoules (GJ) per person',
    gamma: 0.90,
    defaultDurationYears: 5.0,
    descriptionAr: 'مؤشر العمل الميكانيكي والحراري الذي يسخره الإنسان المعاصر لخدمة يومه.',
    snapshot2008: {
      rawValue: 74.8,
      eventDescriptionAr: 'مستوى استهلاك طاقة قياسي للفرد قبل أن يؤدي الركود إلى تباطؤ طفيف في 2009.',
      directSign: 1,
      observedDurationYears: 3.0,
      humanCoverageRatio: 0.70
    },
    benchmarks: [
      { year: 1973, value: 58.0, normalizedStress: 0.1 },
      { year: 1980, value: 60.5, normalizedStress: 0.2 },
      { year: 1990, value: 64.0, normalizedStress: 0.25 },
      { year: 2001, value: 66.8, normalizedStress: 0.35 },
      { year: 2008, value: 74.8, normalizedStress: 0.5 },
      { year: 2020, value: 71.5, normalizedStress: 0.3 },
      { year: 2024, value: 77.0, normalizedStress: 0.6 }
    ]
  },
  {
    id: 's25-container-throughput',
    nameAr: 'حركة مناولة الحاويات البحرية العالمية',
    nameEn: 'Global Container Port Throughput (UNCTAD/World Bank)',
    layer: 'infrastructure',
    source: 'UNCTAD Review of Maritime Transport',
    unit: 'Million TEU',
    gamma: 0.95,
    defaultDurationYears: 4.0,
    descriptionAr: 'المحرك المادي للعولمة ونقل السلع المصنعة والمواد الأولية عبر القارات.',
    snapshot2008: {
      rawValue: 515.0,
      eventDescriptionAr: 'ذروة قياسية غير مسبوقة قبل تجمد حركة الاعتمادات المستندية في الربع الأخير.',
      directSign: 1,
      observedDurationYears: 3.0,
      humanCoverageRatio: 0.75
    },
    benchmarks: [
      { year: 1973, value: 25.0, normalizedStress: 0.0 },
      { year: 1980, value: 50.0, normalizedStress: 0.1 },
      { year: 1990, value: 88.0, normalizedStress: 0.2 },
      { year: 2001, value: 240.0, normalizedStress: 0.4 },
      { year: 2008, value: 515.0, normalizedStress: 0.65 },
      { year: 2020, value: 790.0, normalizedStress: 0.7 },
      { year: 2024, value: 860.0, normalizedStress: 0.8 }
    ]
  },
  {
    id: 's26-air-passenger-traffic',
    nameAr: 'النقل الجوي للركاب عالمياً',
    nameEn: 'Global Air Passengers Carried (ICAO / World Bank)',
    layer: 'infrastructure',
    source: 'ICAO / World Bank WDI (IS.AIR.PSGR)',
    unit: 'Billion Passengers',
    gamma: 0.98,
    defaultDurationYears: 3.0,
    descriptionAr: 'سهولة انتقال البشر وسياحتهم وتواصلهم الشخصي والتجاري عبر العالم.',
    snapshot2008: {
      rawValue: 2.49,
      eventDescriptionAr: 'أعلى حركة سفر دولية ومحلية مسجلة قبل تداعيات أزمة الطيران.',
      directSign: 1,
      observedDurationYears: 3.0,
      humanCoverageRatio: 0.35
    },
    benchmarks: [
      { year: 1973, value: 0.41, normalizedStress: 0.05 },
      { year: 1980, value: 0.64, normalizedStress: 0.1 },
      { year: 1990, value: 1.02, normalizedStress: 0.2 },
      { year: 2001, value: 1.65, normalizedStress: 0.25 },
      { year: 2008, value: 2.49, normalizedStress: 0.5 },
      { year: 2020, value: 1.80, normalizedStress: -0.5 },
      { year: 2024, value: 4.60, normalizedStress: 0.85 }
    ]
  },
  {
    id: 's27-air-freight-traffic',
    nameAr: 'حركة الشحن الجوي العالمي للسلع',
    nameEn: 'Global Air Freight Volume (ICAO / World Bank)',
    layer: 'infrastructure',
    source: 'ICAO / World Bank (IS.AIR.GOOD.MT.K1)',
    unit: 'Billion Ton-Kilometers',
    gamma: 0.98,
    defaultDurationYears: 2.0,
    descriptionAr: 'شريان نقل البضائع الحساسة للوقت كالأدوية والرقائق الإلكترونية وقطع الغيار الحرجة.',
    snapshot2008: {
      rawValue: 162.0,
      eventDescriptionAr: 'مستويات نشاط عالية صمدت حتى سبتمبر 2008 قبل الانكماش السريع.',
      directSign: 1,
      observedDurationYears: 2.0,
      humanCoverageRatio: 0.50
    },
    benchmarks: [
      { year: 1973, value: 20.0, normalizedStress: 0.0 },
      { year: 1980, value: 35.0, normalizedStress: 0.1 },
      { year: 1990, value: 60.0, normalizedStress: 0.2 },
      { year: 2001, value: 118.0, normalizedStress: 0.3 },
      { year: 2008, value: 162.0, normalizedStress: 0.5 },
      { year: 2020, value: 205.0, normalizedStress: 0.6 },
      { year: 2024, value: 235.0, normalizedStress: 0.7 }
    ]
  },
  {
    id: 's28-internet-users',
    nameAr: 'نسبة مستخدمي الإنترنت من سكان العالم',
    nameEn: 'Individuals Using the Internet (% of Population)',
    layer: 'infrastructure',
    source: 'ITU / World Bank WDI (IT.NET.USER.ZS)',
    unit: 'Percentage (%)',
    gamma: 0.99,
    defaultDurationYears: 20.0,
    descriptionAr: 'الانفجار المعرفي والتواصلي الذي ربط العقول البشرية وأتاح العمل والتعليم الرقمي.',
    snapshot2008: {
      rawValue: 23.1,
      eventDescriptionAr: 'تجاوز مليار ونصف إنسان، وانطلاق منصات التواصل والهواتف الذكية التفاعلية.',
      directSign: 1,
      observedDurationYears: 15.0,
      humanCoverageRatio: 0.25
    },
    benchmarks: [
      { year: 1973, value: 0.0, normalizedStress: 0.0 },
      { year: 1980, value: 0.0, normalizedStress: 0.0 },
      { year: 1990, value: 0.05, normalizedStress: 0.0 },
      { year: 2001, value: 8.0, normalizedStress: 0.2 },
      { year: 2008, value: 23.1, normalizedStress: 0.6 },
      { year: 2020, value: 59.5, normalizedStress: 0.9 },
      { year: 2024, value: 67.8, normalizedStress: 0.95 }
    ]
  },
  {
    id: 's29-mobile-cellular',
    nameAr: 'اشتراكات الهاتف المحمول لكل 100 شخص',
    nameEn: 'Mobile Cellular Subscriptions (per 100 people)',
    layer: 'infrastructure',
    source: 'ITU / World Bank (IT.CEL.SETS.P2)',
    unit: 'Subscriptions / 100 people',
    gamma: 0.99,
    defaultDurationYears: 20.0,
    descriptionAr: 'الأداة التمكينية الأسرع انتشاراً في تاريخ الحضارة، واصلة القرى النائية بالخدمات المصرفية والمعلومات.',
    snapshot2008: {
      rawValue: 60.0,
      eventDescriptionAr: 'تجاوز 4 مليارات اشتراك لأول مرة في تاريخ البشرية.',
      directSign: 1,
      observedDurationYears: 15.0,
      humanCoverageRatio: 0.60
    },
    benchmarks: [
      { year: 1973, value: 0.0, normalizedStress: 0.0 },
      { year: 1980, value: 0.01, normalizedStress: 0.0 },
      { year: 1990, value: 0.2, normalizedStress: 0.05 },
      { year: 2001, value: 15.5, normalizedStress: 0.3 },
      { year: 2008, value: 60.0, normalizedStress: 0.7 },
      { year: 2020, value: 106.0, normalizedStress: 0.95 },
      { year: 2024, value: 112.0, normalizedStress: 0.98 }
    ]
  },
  {
    id: 's30-patent-applications',
    nameAr: 'طلبات براءات الاختراع العالمية المودعة',
    nameEn: 'Worldwide Patent Applications (WIPO)',
    layer: 'infrastructure',
    source: 'World Intellectual Property Organization (WIPO)',
    unit: 'Million Applications',
    gamma: 0.99,
    defaultDurationYears: 15.0,
    descriptionAr: 'مؤشر التدفق التكنولوجي وحجم الاستثمار في حلول الغد الطبية والهندسية.',
    snapshot2008: {
      rawValue: 1.91,
      eventDescriptionAr: 'تسجيل مستويات ابتكار قياسية قبيل تباطؤ ميزانيات الأبحاث في العام التالي.',
      directSign: 1,
      observedDurationYears: 10.0,
      humanCoverageRatio: 0.50
    },
    benchmarks: [
      { year: 1973, value: 0.8, normalizedStress: 0.1 },
      { year: 1980, value: 0.85, normalizedStress: 0.15 },
      { year: 1990, value: 1.05, normalizedStress: 0.25 },
      { year: 2001, value: 1.45, normalizedStress: 0.4 },
      { year: 2008, value: 1.91, normalizedStress: 0.6 },
      { year: 2020, value: 3.28, normalizedStress: 0.85 },
      { year: 2024, value: 3.55, normalizedStress: 0.9 }
    ]
  },

  // ==========================================
  // LAYER 3: ENDOGENOUS HUMAN SYSTEM & DECISIONS (20 SERIES)
  // gamma ~ 0.8 - 1.0 (Direct human fabric, policies, contracts, strain)
  // ==========================================
  {
    id: 's31-global-inflation-rate',
    nameAr: 'معدل التضخم العالمي المرجح (أسعار المستهلكين)',
    nameEn: 'Global Inflation Rate (Consumer Prices, Annual %)',
    layer: 'human_system',
    source: 'World Bank / IMF WEO',
    unit: 'Annual %',
    gamma: 0.95,
    defaultDurationYears: 4.0,
    descriptionAr: 'تآكل القوة الشرائية وضرب مدخرات الأسر والدخل الثابت.',
    snapshot2008: {
      rawValue: 8.9,
      eventDescriptionAr: 'صدمة تضخمية متزامنة مع قمة النفط والغذاء ضربت العالم قبل الانكماش الائتماني.',
      directSign: -1,
      observedDurationYears: 3.0,
      humanCoverageRatio: 0.90
    },
    benchmarks: [
      { year: 1973, value: 8.9, normalizedStress: -0.6 },
      { year: 1980, value: 13.9, normalizedStress: -0.9 },
      { year: 1990, value: 8.2, normalizedStress: -0.5 },
      { year: 2001, value: 3.8, normalizedStress: -0.2 },
      { year: 2008, value: 8.9, normalizedStress: -0.7 },
      { year: 2020, value: 1.9, normalizedStress: -0.1 },
      { year: 2024, value: 4.3, normalizedStress: -0.3 }
    ]
  },
  {
    id: 's32-food-price-index',
    nameAr: 'مؤشر أسعار الغذاء الحقيقي لمنظمة فاو',
    nameEn: 'FAO Real Food Price Index (2014-2016=100)',
    layer: 'human_system',
    source: 'Food and Agriculture Organization (FAO)',
    unit: 'Index Points',
    gamma: 0.90,
    defaultDurationYears: 3.0,
    descriptionAr: 'الضغط الفوري على ميزانية العائلات الفقيرة والشرارة الأساسية للاضطرابات الاجتماعية.',
    snapshot2008: {
      rawValue: 106.5,
      eventDescriptionAr: 'أزمة غذاء عالمية واحتجاجات خبز في أكثر من 30 دولة نامية.',
      directSign: -1,
      observedDurationYears: 3.5,
      humanCoverageRatio: 0.85
    },
    benchmarks: [
      { year: 1973, value: 118.0, normalizedStress: -0.8 },
      { year: 1980, value: 105.0, normalizedStress: -0.6 },
      { year: 1990, value: 88.0, normalizedStress: -0.1 },
      { year: 2001, value: 72.0, normalizedStress: 0.3 },
      { year: 2008, value: 106.5, normalizedStress: -0.75 },
      { year: 2020, value: 98.1, normalizedStress: -0.3 },
      { year: 2024, value: 120.5, normalizedStress: -0.7 }
    ]
  },
  {
    id: 's33-real-oil-price',
    nameAr: 'سعر نفط برنت الحقيقي (المعدل للتضخم)',
    nameEn: 'Real Brent Crude Oil Price (2024 Dollars)',
    layer: 'human_system',
    source: 'World Bank Commodity Price Data (Pink Sheet)',
    unit: 'Constant USD / Barrel',
    gamma: 0.90,
    defaultDurationYears: 4.0,
    descriptionAr: 'الضريبة العالمية غير المباشرة على حركة ونقل ومعيشة سكان الكوكب.',
    snapshot2008: {
      rawValue: 124.0,
      eventDescriptionAr: 'بلوغ ذروة تاريخية مطلقة (147$ اسمياً) ثم انهيار حاد إلى 36$ مع ذعر ليمان براذرز.',
      directSign: -1,
      observedDurationYears: 4.0,
      humanCoverageRatio: 0.85
    },
    benchmarks: [
      { year: 1973, value: 28.0, normalizedStress: -0.5 },
      { year: 1980, value: 128.0, normalizedStress: -0.9 },
      { year: 1990, value: 55.0, normalizedStress: -0.3 },
      { year: 2001, value: 38.0, normalizedStress: 0.1 },
      { year: 2008, value: 124.0, normalizedStress: -0.85 },
      { year: 2020, value: 46.0, normalizedStress: 0.0 },
      { year: 2024, value: 82.0, normalizedStress: -0.4 }
    ]
  },
  {
    id: 's34-us-10y-treasury',
    nameAr: 'عائد سندات الخزانة الأمريكية لأجل 10 سنوات',
    nameEn: 'US 10-Year Treasury Benchmark Yield',
    layer: 'human_system',
    source: 'Federal Reserve Bank of St. Louis (FRED)',
    unit: 'Annual %',
    gamma: 0.99,
    defaultDurationYears: 5.0,
    descriptionAr: 'سعر الفائدة الخالي من المخاطر الذي يحدد تكلفة اقتراض الدول والرهون العقارية في العالم.',
    snapshot2008: {
      rawValue: 3.66,
      eventDescriptionAr: 'هبوط حاد ناجم عن الهروب نحو الأمان (Flight to Safety) وذعر الأسواق العالمية.',
      directSign: 0,
      observedDurationYears: 5.0,
      humanCoverageRatio: 0.60
    },
    benchmarks: [
      { year: 1973, value: 6.84, normalizedStress: -0.3 },
      { year: 1980, value: 11.43, normalizedStress: -0.8 },
      { year: 1990, value: 8.55, normalizedStress: -0.4 },
      { year: 2001, value: 5.02, normalizedStress: -0.1 },
      { year: 2008, value: 3.66, normalizedStress: -0.3 },
      { year: 2020, value: 0.89, normalizedStress: 0.2 },
      { year: 2024, value: 4.25, normalizedStress: -0.4 }
    ]
  },
  {
    id: 's35-real-gdp-growth',
    nameAr: 'معدل نمو الناتج المحلي الإجمالي العالمي الحقيقي',
    nameEn: 'Real Global GDP Growth (World Bank / IMF)',
    layer: 'human_system',
    source: 'World Bank (NY.GDP.MKTP.KD.ZG) / IMF WEO',
    unit: 'Annual % Growth',
    gamma: 0.95,
    defaultDurationYears: 4.0,
    descriptionAr: 'المقياس الكلاسيكي لتوسع أو انكماش النشاط الاقتصادي وفرص العمل الكلية.',
    snapshot2008: {
      rawValue: 1.8,
      eventDescriptionAr: 'تباطؤ عنيف من 4.3% في 2007 إلى ركود تام مهد لأكبر انكماش منذ الكساد العظيم.',
      directSign: -1,
      observedDurationYears: 4.0,
      humanCoverageRatio: 0.85
    },
    benchmarks: [
      { year: 1973, value: 6.4, normalizedStress: 0.5 },
      { year: 1980, value: 1.9, normalizedStress: -0.3 },
      { year: 1990, value: 2.8, normalizedStress: 0.0 },
      { year: 2001, value: 2.5, normalizedStress: -0.1 },
      { year: 2008, value: 1.8, normalizedStress: -0.6 },
      { year: 2020, value: -3.1, normalizedStress: -0.9 },
      { year: 2024, value: 3.1, normalizedStress: 0.2 }
    ]
  },
  {
    id: 's36-central-bank-assets',
    nameAr: 'ميزانيات البنوك المركزية الكبرى كنسبة من الناتج',
    nameEn: 'Major Central Banks Total Assets (% of GDP)',
    layer: 'human_system',
    source: 'BIS / Federal Reserve / ECB / BoJ',
    unit: '% of GDP',
    gamma: 1.0,
    defaultDurationYears: 10.0,
    descriptionAr: 'مقياس التدخل النقدي الاستثنائي وطباعة السيولة لإنقاذ المؤسسات المالية المتعثرة.',
    snapshot2008: {
      rawValue: 22.5,
      eventDescriptionAr: 'إطلاق برامج التيسير الكمي (QE1) وتضاعف ميزانية الاحتياطي الفيدرالي لإنقاذ وول ستريت.',
      directSign: 1,
      observedDurationYears: 10.0,
      humanCoverageRatio: 0.70
    },
    benchmarks: [
      { year: 1973, value: 12.0, normalizedStress: 0.0 },
      { year: 1980, value: 13.5, normalizedStress: 0.0 },
      { year: 1990, value: 14.0, normalizedStress: 0.0 },
      { year: 2001, value: 15.2, normalizedStress: 0.1 },
      { year: 2008, value: 22.5, normalizedStress: 0.4 },
      { year: 2020, value: 58.0, normalizedStress: 0.6 },
      { year: 2024, value: 45.0, normalizedStress: 0.2 }
    ]
  },
  {
    id: 's37-oecd-unemployment',
    nameAr: 'معدل البطالة في دول منظمة التعاون الاقتصادي (OECD)',
    nameEn: 'OECD Harmonized Unemployment Rate',
    layer: 'human_system',
    source: 'OECD Main Economic Indicators',
    unit: 'Percentage (%) of Labor Force',
    gamma: 0.98,
    defaultDurationYears: 5.0,
    descriptionAr: 'التهديد المباشر لكرامة الفرد وقدرة الأسرة على سداد التزاماتها اليومية.',
    snapshot2008: {
      rawValue: 6.0,
      eventDescriptionAr: 'انطلاق موجة التسريحات الجماعية في أواخر 2008 لتصل الذروة (8.6%) في 2009/2010.',
      directSign: -1,
      observedDurationYears: 5.0,
      humanCoverageRatio: 0.45
    },
    benchmarks: [
      { year: 1973, value: 3.3, normalizedStress: 0.4 },
      { year: 1980, value: 5.8, normalizedStress: -0.2 },
      { year: 1990, value: 6.1, normalizedStress: -0.2 },
      { year: 2001, value: 6.4, normalizedStress: -0.3 },
      { year: 2008, value: 6.0, normalizedStress: -0.6 },
      { year: 2020, value: 7.2, normalizedStress: -0.7 },
      { year: 2024, value: 4.9, normalizedStress: 0.2 }
    ]
  },
  {
    id: 's38-global-debt-gdp',
    nameAr: 'إجمالي الديون العالمية (العامة والخاصة) نسبة للناتج',
    nameEn: 'Global Debt-to-GDP Ratio (IIF / IMF Global Debt DB)',
    layer: 'human_system',
    source: 'Institute of International Finance / IMF',
    unit: 'Percentage (%) of Global GDP',
    gamma: 1.0,
    defaultDurationYears: 15.0,
    descriptionAr: 'رهن المستقبل وتراكم الالتزامات المالية التي تقيد الاستثمار والخدمات الاجتماعية.',
    snapshot2008: {
      rawValue: 280.0,
      eventDescriptionAr: 'انفجار فقاعة الائتمان الخاص وبدء ترحيل الخسائر إلى الديون السيادية والحكومات.',
      directSign: -1,
      observedDurationYears: 12.0,
      humanCoverageRatio: 0.85
    },
    benchmarks: [
      { year: 1973, value: 140.0, normalizedStress: 0.1 },
      { year: 1980, value: 165.0, normalizedStress: -0.1 },
      { year: 1990, value: 195.0, normalizedStress: -0.2 },
      { year: 2001, value: 245.0, normalizedStress: -0.4 },
      { year: 2008, value: 280.0, normalizedStress: -0.7 },
      { year: 2020, value: 356.0, normalizedStress: -0.95 },
      { year: 2024, value: 335.0, normalizedStress: -0.85 }
    ]
  },
  {
    id: 's39-corporate-defaults',
    nameAr: 'معدل إفلاس وسقوط المؤسسات المالية والشركات',
    nameEn: 'Global Speculative-Grade Corporate Default Rate (S&P)',
    layer: 'human_system',
    source: 'S&P Global Ratings / Moody’s',
    unit: 'Percentage (%)',
    gamma: 0.99,
    defaultDurationYears: 3.0,
    descriptionAr: 'انهيار العقود الاقتصادية، وضياع مستحقات الموردين وتجميد الحسابات المصرفية.',
    snapshot2008: {
      rawValue: 4.15,
      eventDescriptionAr: 'سقوط ليمان براذرز وإفلاس 25 بنكاً أمريكياً وقفزة حادة نحو الذروة (10.5% في 2009).',
      directSign: -1,
      observedDurationYears: 4.0,
      humanCoverageRatio: 0.55
    },
    benchmarks: [
      { year: 1973, value: 1.2, normalizedStress: 0.1 },
      { year: 1980, value: 2.1, normalizedStress: -0.1 },
      { year: 1990, value: 8.5, normalizedStress: -0.7 },
      { year: 2001, value: 9.8, normalizedStress: -0.8 },
      { year: 2008, value: 4.15, normalizedStress: -0.7 },
      { year: 2020, value: 6.8, normalizedStress: -0.6 },
      { year: 2024, value: 3.8, normalizedStress: -0.2 }
    ]
  },
  {
    id: 's40-policy-uncertainty',
    nameAr: 'مؤشر عدم اليقين في السياسات الاقتصادية (GEPU)',
    nameEn: 'Global Economic Policy Uncertainty Index (Baker, Bloom & Davis)',
    layer: 'human_system',
    source: 'Economic Policy Uncertainty Project',
    unit: 'Index Points (Mean=100)',
    gamma: 1.0,
    defaultDurationYears: 3.0,
    descriptionAr: 'شلل القرارات الاستثمارية، وذعر الأسواق من التخبط التشريعي والسياسي.',
    snapshot2008: {
      rawValue: 198.5,
      eventDescriptionAr: 'أعلى مستوى عدم يقين مسجل في التاريخ حتى ذلك الحين جراء قرارات خطط الإنقاذ.',
      directSign: -1,
      observedDurationYears: 4.0,
      humanCoverageRatio: 0.70
    },
    benchmarks: [
      { year: 1973, value: 110.0, normalizedStress: -0.2 },
      { year: 1980, value: 125.0, normalizedStress: -0.3 },
      { year: 1990, value: 130.0, normalizedStress: -0.35 },
      { year: 2001, value: 155.0, normalizedStress: -0.5 },
      { year: 2008, value: 198.5, normalizedStress: -0.85 },
      { year: 2020, value: 340.0, normalizedStress: -1.0 },
      { year: 2024, value: 185.0, normalizedStress: -0.5 }
    ]
  },
  {
    id: 's41-world-population',
    nameAr: 'إجمالي سكان كوكب الأرض',
    nameEn: 'World Population (UN Population Division)',
    layer: 'human_system',
    source: 'UN Department of Economic and Social Affairs (DESA)',
    unit: 'Billion People',
    gamma: 0.99,
    defaultDurationYears: 50.0,
    descriptionAr: 'الكتلة البشرية الحية المستهلكة للموارد والمحتاجة للأمن والغذاء والرعاية.',
    snapshot2008: {
      rawValue: 6.76,
      eventDescriptionAr: 'نمو مستمر بمقدار 80 مليون إنسان إضافي سنوياً زاد من الضغط على الموارد الأساسية.',
      directSign: 0,
      observedDurationYears: 30.0,
      humanCoverageRatio: 1.0
    },
    benchmarks: [
      { year: 1973, value: 3.93, normalizedStress: 0.0 },
      { year: 1980, value: 4.44, normalizedStress: 0.0 },
      { year: 1990, value: 5.31, normalizedStress: 0.0 },
      { year: 2001, value: 6.23, normalizedStress: 0.0 },
      { year: 2008, value: 6.76, normalizedStress: 0.0 },
      { year: 2020, value: 7.84, normalizedStress: 0.0 },
      { year: 2024, value: 8.12, normalizedStress: 0.0 }
    ]
  },
  {
    id: 's42-fertility-rate',
    nameAr: 'معدل الخصوبة الكلي العالمي (المواليد لكل امرأة)',
    nameEn: 'Total Fertility Rate (Births per Woman)',
    layer: 'human_system',
    source: 'UN Population Division / World Bank (SP.DYN.TFRT.IN)',
    unit: 'Births / Woman',
    gamma: 0.99,
    defaultDurationYears: 30.0,
    descriptionAr: 'المقياس العميق لإرادة الإنسان وثقته في مستقبل الحياة ورغبته في إنجاب الذرية.',
    snapshot2008: {
      rawValue: 2.57,
      eventDescriptionAr: 'استمرار الانخفاض الديموغرافي الهيكلي التدريجي نحو مستويات الإحلال.',
      directSign: 0,
      observedDurationYears: 20.0,
      humanCoverageRatio: 0.80
    },
    benchmarks: [
      { year: 1973, value: 4.45, normalizedStress: 0.1 },
      { year: 1980, value: 3.75, normalizedStress: 0.1 },
      { year: 1990, value: 3.25, normalizedStress: 0.0 },
      { year: 2001, value: 2.72, normalizedStress: -0.1 },
      { year: 2008, value: 2.57, normalizedStress: -0.15 },
      { year: 2020, value: 2.30, normalizedStress: -0.3 },
      { year: 2024, value: 2.21, normalizedStress: -0.35 }
    ]
  },
  {
    id: 's43-under5-mortality',
    nameAr: 'معدل وفيات الأطفال دون سن الخامسة (لكل 1000)',
    nameEn: 'Under-5 Mortality Rate (per 1,000 live births)',
    layer: 'human_system',
    source: 'UN IGME / UNICEF / WHO / World Bank',
    unit: 'Deaths / 1,000 live births',
    gamma: 0.90,
    defaultDurationYears: 20.0,
    descriptionAr: 'أقدس وأصدق مقياس لصمود البنية الصحية واللقاحات والمياه النظيفة للأسر.',
    snapshot2008: {
      rawValue: 61.2,
      eventDescriptionAr: 'انخفاض تاريخي متسارع يمثل نجاة ملايين الأطفال مقارنة بعقود السبعينيات والثمانينيات.',
      directSign: 1,
      observedDurationYears: 15.0,
      humanCoverageRatio: 0.90
    },
    benchmarks: [
      { year: 1973, value: 135.0, normalizedStress: -0.8 },
      { year: 1980, value: 115.0, normalizedStress: -0.6 },
      { year: 1990, value: 93.2, normalizedStress: -0.4 },
      { year: 2001, value: 76.5, normalizedStress: -0.1 },
      { year: 2008, value: 61.2, normalizedStress: 0.3 },
      { year: 2020, value: 38.0, normalizedStress: 0.7 },
      { year: 2024, value: 36.5, normalizedStress: 0.75 }
    ]
  },
  {
    id: 's44-life-expectancy',
    nameAr: 'متوسط العمر المتوقع عند الولادة عالمياً',
    nameEn: 'Global Life Expectancy at Birth (Years)',
    layer: 'human_system',
    source: 'UN Population Division / World Bank (SP.DYN.LE00.IN)',
    unit: 'Years',
    gamma: 0.90,
    defaultDurationYears: 30.0,
    descriptionAr: 'المحصلة النهائية لكل مكاسب الطب والحروب والغذاء والتغذية على امتداد عمر الإنسان.',
    snapshot2008: {
      rawValue: 69.4,
      eventDescriptionAr: 'زيادة متواصلة بلغت +11 سنة مقارنة بـ 1970 تعكس تحسن جودة الحياة العامة.',
      directSign: 1,
      observedDurationYears: 20.0,
      humanCoverageRatio: 0.95
    },
    benchmarks: [
      { year: 1973, value: 59.2, normalizedStress: -0.3 },
      { year: 1980, value: 62.8, normalizedStress: -0.1 },
      { year: 1990, value: 65.4, normalizedStress: 0.1 },
      { year: 2001, value: 67.8, normalizedStress: 0.3 },
      { year: 2008, value: 69.4, normalizedStress: 0.5 },
      { year: 2020, value: 72.0, normalizedStress: 0.6 },
      { year: 2024, value: 73.2, normalizedStress: 0.7 }
    ]
  },
  {
    id: 's45-battle-related-deaths',
    nameAr: 'وفيات النزاعات المسلحة والحروب السنوية',
    nameEn: 'Battle-Related Deaths in Armed Conflicts (UCDP)',
    layer: 'human_system',
    source: 'Uppsala Conflict Data Program (UCDP)',
    unit: 'Thousands of Direct Fatalities',
    gamma: 1.0,
    defaultDurationYears: 8.0,
    descriptionAr: 'العنف المباشر المنظم للدول والجماعات، المزهق للأرواح والمدمر للأوطان.',
    snapshot2008: {
      rawValue: 54.0,
      eventDescriptionAr: 'اشتعال حرب جورجيا واستمرار نزاعات العراق وأفغانستان ودارفور.',
      directSign: -1,
      observedDurationYears: 6.0,
      humanCoverageRatio: 0.15
    },
    benchmarks: [
      { year: 1973, value: 120.0, normalizedStress: -0.6 },
      { year: 1980, value: 195.0, normalizedStress: -0.8 },
      { year: 1990, value: 85.0, normalizedStress: -0.4 },
      { year: 2001, value: 45.0, normalizedStress: -0.2 },
      { year: 2008, value: 54.0, normalizedStress: -0.35 },
      { year: 2020, value: 80.0, normalizedStress: -0.5 },
      { year: 2024, value: 165.0, normalizedStress: -0.8 }
    ]
  },
  {
    id: 's46-forcibly-displaced',
    nameAr: 'إجمالي اللاجئين والنازحين قسرياً حول العالم',
    nameEn: 'Forcibly Displaced Population Globally (UNHCR)',
    layer: 'human_system',
    source: 'UNHCR Global Trends Report',
    unit: 'Million People Displaced',
    gamma: 0.98,
    defaultDurationYears: 10.0,
    descriptionAr: 'اقتلاع البشر من مساكنهم، وفقدان الأمان والأرزاق والتشتت في المخيمات.',
    snapshot2008: {
      rawValue: 42.0,
      eventDescriptionAr: 'استقرار نسبي مؤقت عند 42 مليون شخص قبل الانفجار الكبير لما بعد 2011.',
      directSign: -1,
      observedDurationYears: 8.0,
      humanCoverageRatio: 0.20
    },
    benchmarks: [
      { year: 1973, value: 12.0, normalizedStress: -0.1 },
      { year: 1980, value: 20.0, normalizedStress: -0.2 },
      { year: 1990, value: 30.0, normalizedStress: -0.3 },
      { year: 2001, value: 38.0, normalizedStress: -0.4 },
      { year: 2008, value: 42.0, normalizedStress: -0.45 },
      { year: 2020, value: 82.4, normalizedStress: -0.8 },
      { year: 2024, value: 120.0, normalizedStress: -0.95 }
    ]
  },
  {
    id: 's47-global-forest-area',
    nameAr: 'مساحة الغابات العالمية الإجمالية',
    nameEn: 'Total Global Forest Area (FAO FRA)',
    layer: 'human_system',
    source: 'FAO Global Forest Resources Assessment',
    unit: 'Billion Hectares',
    gamma: 0.85,
    defaultDurationYears: 30.0,
    descriptionAr: 'رئة الكوكب وموطن التنوع الحيوي ومخزن الكربون ومنظم دورة المياه.',
    snapshot2008: {
      rawValue: 4.06,
      eventDescriptionAr: 'استمرار فقدان الغابات بمعدل 5 ملايين هكتار سنوياً مدفوعاً بقطع أشجار الأمازون وإندونيسيا.',
      directSign: -1,
      observedDurationYears: 20.0,
      humanCoverageRatio: 0.40
    },
    benchmarks: [
      { year: 1973, value: 4.40, normalizedStress: 0.2 },
      { year: 1980, value: 4.30, normalizedStress: 0.1 },
      { year: 1990, value: 4.23, normalizedStress: 0.0 },
      { year: 2001, value: 4.11, normalizedStress: -0.2 },
      { year: 2008, value: 4.06, normalizedStress: -0.3 },
      { year: 2020, value: 4.01, normalizedStress: -0.45 },
      { year: 2024, value: 3.99, normalizedStress: -0.5 }
    ]
  },
  {
    id: 's48-fossil-co2-emissions',
    nameAr: 'انبعاثات ثاني أكسيد الكربون من الوقود الأحفوري',
    nameEn: 'Global Fossil CO2 Emissions (GCP / CDIAC)',
    layer: 'human_system',
    source: 'Global Carbon Project / CDIAC',
    unit: 'Billion Metric Tons (GtCO2)',
    gamma: 0.99,
    defaultDurationYears: 50.0,
    descriptionAr: 'الناتج العادم للتصنيع البشري الذي يرفع حرارة الغلاف الجوي لعقود قادمة.',
    snapshot2008: {
      rawValue: 32.1,
      eventDescriptionAr: 'مواصلة الارتفاع المتسارع وتباطؤ طفيف في الربع الأخير بسبب الركود.',
      directSign: -1,
      observedDurationYears: 25.0,
      humanCoverageRatio: 0.70
    },
    benchmarks: [
      { year: 1973, value: 16.5, normalizedStress: -0.1 },
      { year: 1980, value: 19.4, normalizedStress: -0.2 },
      { year: 1990, value: 22.7, normalizedStress: -0.3 },
      { year: 2001, value: 25.7, normalizedStress: -0.4 },
      { year: 2008, value: 32.1, normalizedStress: -0.6 },
      { year: 2020, value: 35.3, normalizedStress: -0.7 },
      { year: 2024, value: 37.4, normalizedStress: -0.8 }
    ]
  },
  {
    id: 's49-methane-emissions',
    nameAr: 'انبعاثات غاز الميثان العالمية من الأنشطة البشرية',
    nameEn: 'Global Anthropogenic Methane Emissions (EDGAR)',
    layer: 'human_system',
    source: 'EDGAR Joint Research Centre / NOAA ESRL',
    unit: 'Million Metric Tons CH4',
    gamma: 0.85,
    defaultDurationYears: 12.0,
    descriptionAr: 'غاز دفيئة فائق القوة قصير العمر صادر عن الزراعة وقطاع النفط ومدافن النفايات.',
    snapshot2008: {
      rawValue: 345.0,
      eventDescriptionAr: 'استئناف تسارع تركيزات الميثان في الغلاف الجوي بعد فترة استقرار دامت عقداً.',
      directSign: -1,
      observedDurationYears: 10.0,
      humanCoverageRatio: 0.60
    },
    benchmarks: [
      { year: 1973, value: 240.0, normalizedStress: -0.1 },
      { year: 1980, value: 275.0, normalizedStress: -0.2 },
      { year: 1990, value: 310.0, normalizedStress: -0.3 },
      { year: 2001, value: 325.0, normalizedStress: -0.35 },
      { year: 2008, value: 345.0, normalizedStress: -0.5 },
      { year: 2020, value: 380.0, normalizedStress: -0.65 },
      { year: 2024, value: 395.0, normalizedStress: -0.7 }
    ]
  },
  {
    id: 's50-military-expenditure',
    nameAr: 'الإنفاق العسكري العالمي كنسبة من الناتج',
    nameEn: 'Global Military Expenditure (% of GDP) (SIPRI)',
    layer: 'human_system',
    source: 'Stockholm International Peace Research Institute (SIPRI)',
    unit: '% of World GDP',
    gamma: 1.0,
    defaultDurationYears: 8.0,
    descriptionAr: 'تحويل الموارد الاقتصادية نحو التسلح بدلاً من الصحة والتعليم والتنمية المستدامة.',
    snapshot2008: {
      rawValue: 2.4,
      eventDescriptionAr: 'صعود ملحوظ مدفوعاً بحروب ما بعد 2001 والسباق التسلحي الإقليمي.',
      directSign: -1,
      observedDurationYears: 6.0,
      humanCoverageRatio: 0.65
    },
    benchmarks: [
      { year: 1973, value: 3.8, normalizedStress: -0.7 },
      { year: 1980, value: 3.6, normalizedStress: -0.65 },
      { year: 1990, value: 3.3, normalizedStress: -0.5 },
      { year: 2001, value: 2.2, normalizedStress: -0.2 },
      { year: 2008, value: 2.4, normalizedStress: -0.35 },
      { year: 2020, value: 2.3, normalizedStress: -0.3 },
      { year: 2024, value: 2.5, normalizedStress: -0.45 }
    ]
  }
];
