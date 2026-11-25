# CHAOS — نتائج الجولة الرسمية متعددة المصادر: OECD Institutions/Policy

## Government at a Glance 2025

المصدر الرسمي: https://www.oecd.org/en/publications/government-at-a-glance-2025_0efd0bcd-en.html

الإصدار مؤرخ 19 June 2025 ويقدم مؤشرات وأدوات مبنية على الأدلة حول الحكومة والخدمات العامة والمالية والثقة والمشاركة وصنع السياسات. تعرض الصفحة مؤشرات محددة مثل العجز المالي المتوسط في دول OECD، الثقة، إتاحة datasets الحكومية، مشاركة أصحاب المصلحة، ومؤشر الحكومة الرقمية. تشمل السلسلة إصدارات سابقة من 2009 إلى 2025، لكن المؤشرات ليست panel سنوية متجانسة لكل بُعد؛ بعضها survey أو snapshot أو متقطع حسب الإصدار.

## Product Market Regulation (PMR)

المصدر الرسمي: https://www.oecd.org/en/topics/sub-issues/product-market-regulation.html

توضح OECD أن أحدث تحديث لمؤشرات PMR يشمل 56 اقتصاداً من OECD وغير OECD. وتعرض المؤشرات الإطار التنظيمي لأسواق المنتجات والحواجز الإدارية والمنافسة والتنظيم في الخدمات والشفافية والحوكمة المرتبطة بالمؤسسات المملوكة للدولة. تشير الصفحة إلى أن PMR يقيس بيئات تنظيمية على مدى 25 عاماً، لكن الإصدار المعروض هو تحديث 2023–2024 ولا يثبت وحده تواتراً سنوياً كاملاً لكل اقتصاد أو كل dimension.

## الدلالة البحثية

PMR أقرب إلى policy/institution state من WGI العام، لكنه يظل قياساً تنظيمياً دورياً لا سجلاً زمنياً لكل قرار تشريعي. يمكن بناء حالات `regulatory_regime` أو `institutional_regime` وفق source-defined waves، ولا يجوز تحويل فرق القياس إلى policy shock مؤرخ بدقة أو leader-specific deviation.

## قرار الجولة

1. OECD يضيف مصدراً مؤسسياً مستقلاً مهماً للمقارنة مع WGI.
2. الأولوية العملية هي تثبيت ملف PMR/metadata القابل للتنزيل وتواريخ كل wave قبل بناء adapter.
3. Government at a Glance مفيد لبناء سياق مالي/حكومي، لكنه لا ينبغي دمجه آلياً مع WGI أو PMR كمتغير مؤسسي موحد.
4. لا تُستخدم أي نتائج OECD في Edge أو Composer قبل تثبيت coverage والـwave dates والـunit وتعريف missingness.
