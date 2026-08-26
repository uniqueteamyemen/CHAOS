# تقرير ثبات عائلة Regime عبر متغيرات الحجم وتقسيمات الكيانات

## الخلاصة التنفيذية

جُمّدت صيغة الـregime قبل التشغيل باعتبارها:

```text
high current growth regime
AND
bounded population / scale regime
→ material drop within 3 years
```

ثم استُبدل متغير الحجم بثلاثة proxies محددة مسبقاً: `population`، و`GDP per capita`، و`energy per GDP`. استُخدمت ست عتبات لكل proxy وست عتبات لنمو الهدف، أي 108 خلايا، مع ثلاث نوافذ زمنية وentity-holdout مستقل من خمس مجموعات.

النتيجة: **لم تختفِ عائلة regime عند استبدال population بالكامل**. بقيت فكرة «نمو حالي مرتفع + قيد على مقياس/حجم» قوية مع population وenergy per GDP، بينما كان GDP per capita أضعف بوضوح. كما بقيت الصيغة قوية في entity-holdout؛ أي أن الأداء لم يعتمد فقط على نفس الكيانات التي ظهرت في fit. ومع ذلك، لا تزال هذه association داخل `macro_plus_eia_energy` وليست نمطاً عاماً مثبتاً، لأن proxies الثلاثة ليست مستقلة تماماً وقد تشترك في أثر مستوى التنمية أو بنية الكيانات.

## تصميم المقارنة

| البعد | النطاق |
|---|---|
| Outcome | `material_drop_2pp` عند `t+3` |
| Growth thresholds | 3، 4، 5، 6، 7، 8 |
| Population thresholds | 25m، 50m، 75m، 100m، 150m، 250m |
| GDP per capita thresholds | 1,000، 2,000، 2,500، 3,000، 5,000، 10,000 |
| Energy per GDP thresholds | 1، 2، 4، 6، 8، 10 |
| إجمالي الخلايا | 108 |
| الزمن | ثلاث rolling folds قبل 2020 |
| entity-holdout | خمس مجموعات ثابتة بالـSHA-256 للكيان |
| locked test | مغلق ولم يُستخدم |

كل العتبات أُعلنت قبل قراءة نتائج validation. لم تُعاد إضافة العتبة الدقيقة السابقة `4.9606643 / 77m` إلى أي شبكة.

## النتائج عبر النوافذ الزمنية

أفضل خلية داخل كل proxy، بعد حساب متوسط validation عبر النوافذ الثلاث:

| Proxy | أفضل target threshold | أفضل size threshold | Mean BA | SD BA | Mean F1 | متوسط support |
|---|---:|---:|---:|---:|---:|---:|
| Population | 4.0 | 75m | 0.7276 | 0.0457 | 0.5138 | 171.3 |
| Energy per GDP | 4.0 | 10 | 0.7214 | 0.0359 | 0.4940 | 204.7 |
| GDP per capita | 3.0 | 10,000 | 0.6776 | 0.0183 | 0.4451 | 221.0 |

النتيجة لا تعتمد على population وحده: `energy_per_gdp` اقترب من أداء population، بينما `GDP per capita` بقي أدنى بنحو خمس نقاط Balanced Accuracy تقريباً. هذا يدعم وجود regime عريض مرتبط بالنمو الحالي ومقياس اقتصادي/طاقي، لكنه لا يحدد أي proxy هو السبب الحقيقي.

## entity-holdout مستقل

في هذا الاختبار لم تُستخدم الكيانات نفسها في المجموعتين. قُسمت الكيانات إلى خمس مجموعات ثابتة قبل حساب المقاييس، ثم قيس الأداء عبر ثلاث نوافذ زمنية؛ أي 15 مجموعة تقييم مستقلة لكل خلية.

| Proxy | أفضل خلية داخل entity-holdout | Mean BA | SD BA | Mean F1 | متوسط support | مجموعات ذات support |
|---|---|---:|---:|---:|---:|---:|
| Population | growth > 4، population[t-2] ≤ 250m | 0.7275 | 0.0590 | 0.5018 | 39.5 | 15/15 |
| Energy per GDP | growth > 4، energy/GDP[t-2] ≤ 10 | 0.7235 | 0.0596 | 0.4961 | 40.9 | 15/15 |
| GDP per capita | growth > 4، GDP per capita[t-2] ≤ 10,000 | 0.6760 | 0.0682 | 0.4529 | 35.1 | 15/15 |

وعند تثبيت خلية population الأصلية نفسها `4 / 75m` على entity-holdout، كان Mean BA=`0.7250` وMean F1=`0.5113`. هذا قريب جداً من أفضل population cell، ويعني أن النتيجة ليست مجرد اختيار حد population واحد بعد رؤية الكيانات.

## تفسير النتيجة

لدينا الآن ثلاثة مستويات من الدليل:

| المستوى | النتيجة |
|---|---|
| Population grid | regime قوي نسبياً حول growth > 4 وbounded population |
| Proxy substitution | Energy/GDP يحافظ على الإشارة؛ GDP per capita أضعف |
| Entity-holdout | الأداء يبقى قريباً من 0.72 BA في population وenergy/GDP على كيانات غير مستخدمة في fit |

القراءة الأكثر تحفظاً هي أن **عائلة regime تبدو مرتبطة بحالة نمو مرتفع مع مقياس اقتصادي/طاقي مقيد، لا بحد population وحده**. لكن population وenergy/GDP وGDP per capita قد تحمل معلومات مشتركة عن الحجم، التنمية، البنية الإنتاجية، أو تركيب الكيانات. لذلك لا نستطيع بعد فصل مساهماتها سببيًا.

## ما الذي تغيّر؟

الخلية population `4 / 75m` بقيت قريبة من الأفضل في entity-holdout، لكن `4 / 250m` أصبح الأفضل قليلاً داخل أفضل خلية population على holdout. هذا لا يعني أن 250m هو threshold الصحيح؛ بل يوضح أن عائلة bounded-scale أوسع من threshold واحد، وأن اختيار threshold من نفس holdout لا ينبغي أن يتحول إلى ادعاء نهائي.

كما أن GDP per capita لم يحافظ على الأداء نفسه. لذلك لا يصح القول إن أي متغير «حجم» بديل يثبت الفكرة بنفس القوة. الدليل الحالي أقوى لـpopulation وenergy per GDP، وأضعف لـGDP per capita.

## القرار

أعتبر عائلة الـregime **مرشحاً عابراً للـproxy جزئياً**:

```text
high current growth
AND
bounded scale / intensity measure
→ material drop within 3 years
```

لكنها لم تصبح بعد `validated pattern`. قبل فتح locked test، يلزم تجميد proxy والعتبة من الآن، ثم تنفيذ اختبار نهائي مستقل لا يسمح بإعادة اختيار أفضل proxy أو threshold بعد رؤية test. الخيار الأكثر منطقية للاختبار النهائي هو تشغيل مسارين مجمدين مسبقاً:

1. Population regime: `target[t] > 4` و`population[t-2] <= 75m`.
2. Energy-intensity regime: `target[t] > 4` و`energy_per_gdp[t-2] <= 10`.

إذا نجح أحدهما في locked test دون إعادة الاختيار، نسجل نجاحاً تنبؤياً خارج العينة. إذا فشلا، نحتفظ بالنتيجة كـpanel-specific association رغم قوتها في validation وentity-holdout.

لم يُفتح locked test في هذه المرحلة، ولم تُعدل البيانات الخام، ولم تُستخدم imputation أو normalization.
