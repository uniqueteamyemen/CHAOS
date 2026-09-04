// src/data/transition2013Data.ts
// Empirical Benchmark Data for 2013 across all 50 Fleet Series
// Exactly 5 years post-2008 crisis (The Out-of-Sample Transition Test: 2008 -> 2013)

export interface Year2013DataPoint {
  seriesId: string;
  value2013: number;
  normalizedStress2013: number; // -1 to +1
  contextAr: string;
}

export const FLEET_2013_TRANSITION_DATA: Record<string, Year2013DataPoint> = {
  // Layer 1: Nature (s01 - s10)
  's01-solar-cycle': {
    seriesId: 's01-solar-cycle',
    value2013: 65.0,
    normalizedStress2013: -0.05,
    contextAr: 'ذروة ضعيفة نسبياً للدورة الشمسية 24 دون عواصف شمسية قاهرة.'
  },
  's02-enso-nino34': {
    seriesId: 's02-enso-nino34',
    value2013: -0.3,
    normalizedStress2013: 0.0,
    contextAr: 'طور حيادي للمحيط الهادئ دون نينيو أو لانينا حادة.'
  },
  's03-nao-index': {
    seriesId: 's03-nao-index',
    value2013: 0.4,
    normalizedStress2013: 0.0,
    contextAr: 'تذبذب أطلسي معتدل واعتدال مناخي في غرب أوروبا.'
  },
  's04-global-seismic-energy': {
    seriesId: 's04-global-seismic-energy',
    value2013: 14.5,
    normalizedStress2013: -0.2,
    contextAr: 'زلزال بحر أوخوتسك العميق (M8.3) دون تسونامي مدمر للمناطق السكنية.'
  },
  's05-global-temp-anomaly': {
    seriesId: 's05-global-temp-anomaly',
    value2013: 0.68,
    normalizedStress2013: -0.25,
    contextAr: 'استمرار الصعود الحراري بمعدل +0.68 مئوية فوق خط الأساس.'
  },
  's06-global-precipitation': {
    seriesId: 's06-global-precipitation',
    value2013: 8.5,
    normalizedStress2013: 0.1,
    contextAr: 'هطول مطري إيجابي دعم مواسم الحصاد في نصف الكرة الشمالي.'
  },
  's07-arctic-ice-extent': {
    seriesId: 's07-arctic-ice-extent',
    value2013: 5.05,
    normalizedStress2013: -0.25,
    contextAr: 'ارتداد طفيف عن القاع القياسي لعام 2012 (3.4 مليون كم²).'
  },
  's08-sea-level-rise': {
    seriesId: 's08-sea-level-rise',
    value2013: 62.5,
    normalizedStress2013: -0.2,
    contextAr: 'ارتفاع تدريجي متواصل بمعدل 3.2 مم/سنة.'
  },
  's09-volcanic-stratospheric-aod': {
    seriesId: 's09-volcanic-stratospheric-aod',
    value2013: 0.003,
    normalizedStress2013: 0.05,
    contextAr: 'هدوء بركاني ونفاذية شمسية طبيعية دون تأثير حجب.'
  },
  's10-cosmic-rays': {
    seriesId: 's10-cosmic-rays',
    value2013: 5900,
    normalizedStress2013: 0.0,
    contextAr: 'تدفق كوني متوسط مع صعود النشاط الشمسي النسبي.'
  },

  // Layer 2: Infrastructure (s11 - s30)
  's11-wheat-production': {
    seriesId: 's11-wheat-production',
    value2013: 716.0,
    normalizedStress2013: 0.65,
    contextAr: 'محصول قمح قياسي تاريخي تجاوز حاجز 700 مليون طن.'
  },
  's12-rice-production': {
    seriesId: 's12-rice-production',
    value2013: 478.0,
    normalizedStress2013: 0.6,
    contextAr: 'وفرة محصولية عالية في آسيا أمنت استقرار أسعار الأرز.'
  },
  's13-corn-production': {
    seriesId: 's13-corn-production',
    value2013: 1018.0,
    normalizedStress2013: 0.7,
    contextAr: 'كسر حاجز المليار طن عالمياً لأول مرة بفضل التوسع الزراعي.'
  },
  's14-soybean-production': {
    seriesId: 's14-soybean-production',
    value2013: 283.0,
    normalizedStress2013: 0.55,
    contextAr: 'صعود إنتاج البروتين النباتي وتوسع زراعة الصويا في البرازيل.'
  },
  's15-grain-stocks-to-use': {
    seriesId: 's15-grain-stocks-to-use',
    value2013: 24.5,
    normalizedStress2013: 0.1,
    contextAr: 'تعافي مخزونات الحبوب العالمية وصمام الأمان الغذائي من قاع 2008 (19.8%).'
  },
  's16-meat-production': {
    seriesId: 's16-meat-production',
    value2013: 310.0,
    normalizedStress2013: 0.6,
    contextAr: 'نمو استهلاك اللحوم والدواجن في الاقتصادات الصاعدة.'
  },
  's17-nitrogen-fertilizer': {
    seriesId: 's17-nitrogen-fertilizer',
    value2013: 108.0,
    normalizedStress2013: 0.35,
    contextAr: 'تراجع تكاليف الأسمدة مع هدوء أسعار الغاز الطبيعي بعد طفرة الغاز الصخري.'
  },
  's18-crude-oil-production': {
    seriesId: 's18-crude-oil-production',
    value2013: 86.8,
    normalizedStress2013: 0.15,
    contextAr: 'انفجار إنتاج النفط الصخري الأمريكي وكسر اختناق العرض العالمي.'
  },
  's19-coal-consumption': {
    seriesId: 's19-coal-consumption',
    value2013: 158.0,
    normalizedStress2013: -0.3,
    contextAr: 'بلوغ ذروة استهلاك الفحم التاريخية في الصين والتصنيع الثقيل.'
  },
  's20-gas-consumption': {
    seriesId: 's20-gas-consumption',
    value2013: 3360.0,
    normalizedStress2013: 0.55,
    contextAr: 'تسارع التحول نحو محطات الغاز الرخيصة وتراجع انبعاثات الفحم بأمريكا.'
  },
  's21-hydro-generation': {
    seriesId: 's21-hydro-generation',
    value2013: 3780.0,
    normalizedStress2013: 0.6,
    contextAr: 'دخول سدود كبرى جديدة حيز الخدمة في الصين وأمريكا الجنوبية.'
  },
  's22-nuclear-generation': {
    seriesId: 's22-nuclear-generation',
    value2013: 2460.0,
    normalizedStress2013: 0.25,
    contextAr: 'انكماش الطاقة النووية عقب حادثة فوكوشيما 2011 وإغلاق مفاعلات اليابان وألمانيا.'
  },
  's23-electricity-access': {
    seriesId: 's23-electricity-access',
    value2013: 85.2,
    normalizedStress2013: 0.65,
    contextAr: 'توسع كهربة القرى والمناطق الريفية ليصل النفاذ إلى 85% من البشر.'
  },
  's24-per-capita-energy': {
    seriesId: 's24-per-capita-energy',
    value2013: 75.5,
    normalizedStress2013: 0.5,
    contextAr: 'استقرار استهلاك الطاقة للفرد عالمياً عند مستويات قياسية.'
  },
  's25-container-throughput': {
    seriesId: 's25-container-throughput',
    value2013: 650.0,
    normalizedStress2013: 0.7,
    contextAr: 'تعافي ونمو حركة الشحن البحري بالحاويات بنسبة +26% مقارنة بـ 2008.'
  },
  's26-air-passenger-traffic': {
    seriesId: 's26-air-passenger-traffic',
    value2013: 3.05,
    normalizedStress2013: 0.65,
    contextAr: 'تجاوز 3 مليارات راكب جوي سنوياً لأول مرة في تاريخ الطيران.'
  },
  's27-air-freight-traffic': {
    seriesId: 's27-air-freight-traffic',
    value2013: 182.0,
    normalizedStress2013: 0.55,
    contextAr: 'نمو التجارة الإلكترونية العابرة للقارات وشحن الأجهزة الذكية.'
  },
  's28-internet-users': {
    seriesId: 's28-internet-users',
    value2013: 36.5,
    normalizedStress2013: 0.75,
    contextAr: 'انفجار استخدام الهواتف الذكية وثورة التطبيقات (قفزة من 23% إلى 36.5%).'
  },
  's29-mobile-cellular': {
    seriesId: 's29-mobile-cellular',
    value2013: 92.5,
    normalizedStress2013: 0.85,
    contextAr: 'اقتراب اشتراكات المحمول من معدل هاتف لكل إنسان على الكوكب.'
  },
  's30-patent-applications': {
    seriesId: 's30-patent-applications',
    value2013: 2.57,
    normalizedStress2013: 0.7,
    contextAr: 'تسارع طلبات براءات الاختراع عالمياً وتفوق الصين في حجم الإيداع.'
  },

  // Layer 3: Endogenous Human System (s31 - s50)
  's31-global-inflation-rate': {
    seriesId: 's31-global-inflation-rate',
    value2013: 2.6,
    normalizedStress2013: 0.1,
    contextAr: 'هدوء تضخمي كبير وانتقال إلى مرحلة الخوف من الانكماش السعري في أوروبا.'
  },
  's32-food-price-index': {
    seriesId: 's32-food-price-index',
    value2013: 120.0,
    normalizedStress2013: -0.4,
    contextAr: 'تراجع تدريجي لأسعار الغذاء عن ذروة 2011 مع تحسن المحاصيل.'
  },
  's33-real-oil-price': {
    seriesId: 's33-real-oil-price',
    value2013: 108.0,
    normalizedStress2013: -0.5,
    contextAr: 'استقرار نسبي مرتفع فوق 100 دولار للبرميل قبل انهيار 2014.'
  },
  's34-us-10y-treasury': {
    seriesId: 's34-us-10y-treasury',
    value2013: 2.35,
    normalizedStress2013: -0.15,
    contextAr: 'صدمة التلويح بتقليص التيسير الكمي (Taper Tantrum) وقفزة مؤقتة في الفائدة.'
  },
  's35-real-gdp-growth': {
    seriesId: 's35-real-gdp-growth',
    value2013: 2.8,
    normalizedStress2013: 0.1,
    contextAr: 'تعافٍ عالمي بطيء وغير متكافئ مع بقاء أوروبا في ركود الديون السيادية.'
  },
  's36-central-bank-assets': {
    seriesId: 's36-central-bank-assets',
    value2013: 28.5,
    normalizedStress2013: 0.35,
    contextAr: 'استمرار التيسير الكمي (QE3 في أمريكا) وتصريح دراغي الشهير بحماية اليورو.'
  },
  's37-oecd-unemployment': {
    seriesId: 's37-oecd-unemployment',
    value2013: 7.9,
    normalizedStress2013: -0.55,
    contextAr: 'بطالة عنيدة مرتفعة، ووصول بطالة الشباب في جنوب أوروبا إلى 50%.'
  },
  's38-global-debt-gdp': {
    seriesId: 's38-global-debt-gdp',
    value2013: 295.0,
    normalizedStress2013: -0.75,
    contextAr: 'ترحيل خسائر أزمة 2008 إلى الموازنات العامة وتفاقم الديون السيادية.'
  },
  's39-corporate-defaults': {
    seriesId: 's39-corporate-defaults',
    value2013: 2.1,
    normalizedStress2013: 0.05,
    contextAr: 'انخفاض معدلات الإفلاس بفضل وفرة السيولة الرخيصة من البنوك المركزية.'
  },
  's40-policy-uncertainty': {
    seriesId: 's40-policy-uncertainty',
    value2013: 140.0,
    normalizedStress2013: -0.4,
    contextAr: 'تراجع عدم اليقين عن ذروة 2008 و2011 رغم أزمة الهاوية المالية الأمريكية.'
  },
  's41-world-population': {
    seriesId: 's41-world-population',
    value2013: 7.21,
    normalizedStress2013: 0.0,
    contextAr: 'تجاوز 7.2 مليار إنسان واستمرار النمو السكاني بنحو 83 مليون سنوياً.'
  },
  's42-fertility-rate': {
    seriesId: 's42-fertility-rate',
    value2013: 2.47,
    normalizedStress2013: -0.2,
    contextAr: 'استمرار الانحدار التدريجي للخصوبة مع تمدن المجتمعات.'
  },
  's43-under5-mortality': {
    seriesId: 's43-under5-mortality',
    value2013: 48.0,
    normalizedStress2013: 0.5,
    contextAr: 'انخفاض قياسي لوفيات الأطفال إلى ما دون 50 لكل ألف ولادة حية عالمياً.'
  },
  's44-life-expectancy': {
    seriesId: 's44-life-expectancy',
    value2013: 71.3,
    normalizedStress2013: 0.6,
    contextAr: 'صعود متوسط العمر عالمياً متجاوزاً 71 عاماً بفضل مكاسب الصحة العامة.'
  },
  's45-battle-related-deaths': {
    seriesId: 's45-battle-related-deaths',
    value2013: 75.0,
    normalizedStress2013: -0.5,
    contextAr: 'اشتعال الحرب الأهلية في سوريا وتصاعد العنف في الشرق الأوسط بعد الربيع العربي.'
  },
  's46-forcibly-displaced': {
    seriesId: 's46-forcibly-displaced',
    value2013: 51.2,
    normalizedStress2013: -0.6,
    contextAr: 'كسر حاجز 50 مليون لاجئ ونازح قسرياً للمرة الأولى منذ الحرب العالمية الثانية.'
  },
  's47-global-forest-area': {
    seriesId: 's47-global-forest-area',
    value2013: 4.04,
    normalizedStress2013: -0.35,
    contextAr: 'استمرار فقدان الغابات المطيرة بوتيرة بطيئة نسبياً.'
  },
  's48-fossil-co2-emissions': {
    seriesId: 's48-fossil-co2-emissions',
    value2013: 35.3,
    normalizedStress2013: -0.7,
    contextAr: 'تسجيل قمة جديدة لانبعاثات ثاني أكسيد الكربون (35.3 مليار طن).'
  },
  's49-methane-emissions': {
    seriesId: 's49-methane-emissions',
    value2013: 360.0,
    normalizedStress2013: -0.55,
    contextAr: 'استمرار تصاعد انبعاثات الميثان من قطاع النفط والزراعة.'
  },
  's50-military-expenditure': {
    seriesId: 's50-military-expenditure',
    value2013: 2.3,
    normalizedStress2013: -0.3,
    contextAr: 'استقرار الإنفاق العسكري كنسبة من الناتج مع انسحاب القوات جزئياً من العراق.'
  }
};
