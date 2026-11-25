# ملحق V2 — اقتناء IMF IMTS وتوسعة اعتماد الشركاء

**الجولة:** `20260827_BROWSER_DEEP_RESEARCH`  
**الملحق:** `IMF_IMTS_V2_ADDENDUM_AR.md`  
**التاريخ:** 2026-08-27  
**الحالة:** مكتمل للتدقيق؛ لا يبدّل نتائج V1 أو baseline.

## الغرض

هذا ملحق versioned للرواية التاريخية السابقة، وليس استبدالاً لها. يثبت ما حدث عند توسيع مسار IMF International Trade in Goods Statistics (IMTS) من اقتناء محدود إلى اقتناء XG على نطاق reporters مؤهلين ببيانات WDI، ثم تشغيل عقد اعتماد الشركاء V2. المصدر الرسمي هو [بطاقة IMF IMTS][1]، مع بنية SDMX الرسمية المسجلة في artifacts الجولة.

## ما تم اقتناؤه فعلياً

أظهر profile الرسمي لـ`CL_IMTS_COUNTRY` عدد `359` code. بعد بوابة الجاهزية المرتبطة بتوفر WDI GDP growth في الفترة المطلوبة، أصبح عدد reporters المرشحين للاقتناء `139`. جرت محاولة XG+MG الموسعة عبر `139` طلباً، لكنها أعادت `HTTP 403`؛ سُجلت هذه النتيجة كفشل وصول/صلاحية للمسار، وليست دليلاً على غياب بيانات.

بعد ذلك استُخدم المسار الرسمي XG-only بحد `limit=5000`. نجحت `139/139` طلبات بحالة `HTTP 200`، وبلغ مجموع الاستجابات الخام `311,818,266` bytes. بقيت الاستجابات الخام immutable خارج Git، مع حفظ روابط الطلبات والرؤوس وSHA في ملخص الاقتناء `IMF_IMTS_WDI_READY_XG_ACQUISITION_SUMMARY_V2.json`.

الـadapter المشتق أنتج `515,663` observation rows، وظهر فيه `136` reporter و`240` counterpart code عبر `2000–2024`. لا تمثل هذه observations GDP outcomes مستقلة، ولا تتضمن imputation أو normalization أو source averaging أو تحويل تردد.

## عقد اعتماد الشركاء V2

استُخدمت نافذة `2000–2004` لاختيار candidate pool من أعلى عشرة شركاء حسب حصة صادرات IMTS الخام، ثم active set من أعلى خمسة. بعد تطبيق شرط اكتمال candidate pool، دخل التشغيل `135` reporter. استُخدمت confirmation years `2018–2021`، ونتجت `77` confirmation exposures عبر `48` reporter في `7` مناطق World Bank.

النتيجة الرسمية للعقد هي **`rejected`**. كانت فروق مخاطر confirmation سالبة عند horizons 1/2/3: `-0.1493506494`، `-0.2164502165`، و`-0.1212121212` على الترتيب؛ وبذلك لم يظهر انتقال موجب قابل للترقية. حقق partner-identity null كثافة اختبارية أفضل من V1، إذ نتجت `10,000` replicate و`715` إحصائية فريدة و`SD=0.0232752598`، لكن قيمة `p=0.9884011599` لم تدعم تمييزاً عن null. كما كانت `outcome-null p=0.99940006` و`time-placebo p=0.99920016`. بلغ متوسط cluster bootstrap `-0.10524829` وفاصل 95% هو `[-0.16760485,-0.03797355]`، لكنه لا يحول النتيجة السلبية إلى دليل سببي أو runtime evidence.

## قرار الحوكمة

مر TransitionEvidence V2 عبر schema validation وsupervisor admission وevidence graph وpattern compiler وfinal supervisor gate. بقي السجل في quarantine لأنه `rejected`، ولم يدخل shared composition بوزن إيجابي. اللقطة النهائية هي `57` graph nodes و`58` graph edges، مع `2` supported-predictive records قديمة فقط، و`27` quarantined records، و`0` runtime-eligible patterns، و`0` causal claims. اجتاز QA manifest بحالة `pass`.

سُجل انحراف حوكمي منفصل لأن العقد كان يحمل `draft_for_review` عند وقت التشغيل رغم التفويض الصريح بتنفيذ مقترحات توسعة IMTS. هذا لا يغيّر العقد أو النتائج؛ أي إعادة للسؤال نفسه تحتاج عقد V3 جديداً frozen قبل التشغيل authoritative.

## سياسة الملفات الكبيرة وإعادة البناء

الـaggregate المشتق `IMF_IMTS_XG_OBSERVED_RECORDS_2000_2024.csv` حجمه نحو `128MB`، لذلك بقي ignored محلياً ولا يدخل commit. أُنشئت بدلاً منه `136` reporter shards، أكبرها `1,446,029` bytes، مع `IMF_IMTS_XG_OBSERVATION_SHARDS_MANIFEST_V2.json` الذي يحمل row counts وbytes وSHA وSHA المصدر الأحادي وسياسة reconstruction. الخام يظل خارج Git؛ هذه السياسة لا تغيّر أي قيمة.

## الخلاصة

وسّعت V2 كثافة الدليل والتغطية، وحولت identity null من حالة degenerate إلى null قابل للفحص، لكنها لم تنتج Edge قابلة للتركيب. لذلك يُغلق سؤال V2 الحالي دون threshold tuning أو إعادة تشغيل لنفس العقد. الفجوة التالية ليست تحسين النتيجة قسراً، بل مصدر أو بنية مستقلة تغيّر السؤال، مثل source-native partner substitution أو asymmetry بين export dependence وimport dependence، بعقد جديد مستقل.

[1]: https://data.imf.org/en/datasets/IMF.STA:IMTS "IMF International Trade in Goods by partner country (IMTS)"
