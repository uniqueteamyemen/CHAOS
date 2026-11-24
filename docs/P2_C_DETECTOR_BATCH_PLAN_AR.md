# P2-C — دفعة الكواشف التالية

**الحالة:** بدء التنفيذ — تصميم نطاق وبوابات قبول  
**الفرع:** `feat/p2-c-detector-batch-v1`  
**الأصل:** `main-phase2` عند دمج P2-B: `3c8eab34927640be2fb433efb77467cb9c1e31e2`

## 1. الهدف

إضافة مرشحين أقوى لاكتشاف التحولات الاقتصادية، مع إبقاء P2-B مرجعاً ثابتاً للمقارنة. لا تُعدّل هذه الدفعة ملفات `experiments/**` أو ملفات `structural_engine/isolated_break_detector_v1/**` أو نتائج P2-B المنشورة.

مدخل المقارنة هو نفس cohort المثبت: 509 سلاسل (51 Pink Sheet و458 GEM)، وبصمة المصدر والبروتوكول نفسيهما ما لم يصدر قرار versioned مستقل بتغييرهما.

## 2. تصنيف المرشحين — لا نخلط الفئات

| المكوّن | طبيعته | مسار التقييم |
|---|---|---|
| FOCuS | كاشف online لتغير المتوسط، يختبر أحجام/مقادير تغير متعددة | منافسة online مع prefix replay |
| BOCPD | كاشف Bayesian online لاحتمال بداية run جديد | منافسة online مع posterior calibration وprefix replay |
| Post-Quiet Huber | كاشف sequential robust بعد نافذة quiet | منافسة online، اتجاهان، مقاومة outliers |
| R-FPOP | خوارزمية robust penalized segmentation / retrospective | مسار segmentation مستقل؛ لا ترتب مع online إلا إذا كان زمن القرار causal وممثلاً صراحة |
| Bartlett LRV | مقدّر long-run variance باستخدام Bartlett kernel | مكوّن معايرة/تطبيع، وليس detector arm مستقلاً |

**قرار معماري:** لا نسجل Bartlett LRV على أنه كاشف يصدر أحداثاً. نقارن أثره كمقدّر scale داخل Post-Quiet Huber (ومتى كان مناسباً داخل FOCuS) مقابل MAD baseline. ويظل مقياس LRV نفسه في diagnostics.

**قرار R-FPOP:** يجب الفصل بين `estimated_change_index` (موضع التغير المقدّر) و`detection_index` (أول وقت أصبحت فيه النتيجة قابلة للإصدار). لا يجوز استخدام موضع التغير التاريخي بديلاً عن وقت الإنذار. إن تعذر توفير مسار prefix-causal صحيح، يبقى R-FPOP في تقرير segmentation منفصل ولا يدخل ترتيب online.

## 3. عقد التشغيل

كل online runner:
- يستقبل مصفوفة أحادية البعد finite فقط، ولا يقرأ أي suffix بعد زمن إصدار الحدث.
- يعيد `hits` بعقد موحد: `index` = زمن إصدار الإنذار، `sign` = `-1|+1`، واسم detector.
- يجوز أن يعيد `events` مع `start_index` وحقول تشخيصية؛ أي breakpoint تقديري يخزن منفصلاً عن زمن الإنذار.
- يصرّح بـ `ABSTAIN` وسبب الامتناع عند عدم كفاية البيانات أو فساد/صفر scale؛ لا يحوّل الامتناع إلى لا-إنذار.
- يمر باختبارات prefix replay وfuture-suffix mutation. يجب ألا يظهر hit في البيانات الكاملة ثم يختفي عند إعادة التشغيل على `x[:t+1]`.

لكل runner وصف versioned قابل للتسلسل، وجميع المعاملات المؤثرة على النتيجة تظهر في manifest.

## 4. بروتوكول القياس

تُثبت شروط P2-B للمقارنة العادلة:
- quiet calibration = أول 40 مشاهدة.
- حقن تحول دائم موجب وسالب بمقدار 3×MAD للنافذة quiet، عند 70% من السلسلة.
- stationary bootstrap بمتوسط كتلة 12؛ وتُنشر احتمالات null بوصفها **تشخيصات مشروطة** لا operational FPR.
- فصل النتائج حسب Pink Sheet وGEM، مع إجمالي لا يخفي اختلاف cohort.
- الإبلاغ عن P(≥1 alarm)، الأحداث لكل replicate، الحساسية، miss rate، pre-onset alarm، wrong direction، median وP90 delay، وABSTAIN.
- لا تحفظ القيم الخام في artifacts.

لا تُعاير thresholds على holdout. تُحدد مجموعة تطوير ومجموعة تحقق مستقلة ببذور منفصلة، ويثبت seed ledger قبل التشغيل الكامل.

## 5. اختبارات الضغط المطلوبة قبل تشغيل 509 سلسلة

1. لا تغير مع صفر outlier، وتغير موجب/سالب متناظر.
2. outlier مفرد شديد مقابل تحول دائم؛ يجب ألا يتعامل الكاشف robust مع spike كأنه regime جديد.
3. ضجيج Student-t heavy-tailed وvariance jump دون mean shift.
4. autocorrelation/serial dependence لقياس فائدة Bartlett LRV.
5. تغيرات متعددة متتابعة، رجوع إلى baseline، وتغير تدريجي.
6. quiet scale صفري أو نافذة قصيرة: ABSTAIN موثق.
7. causal prefix replay وfuture-suffix mutation لكل hit/event.
8. حدود runtime والذاكرة على أطوال تصل إلى 539 مشاهدة، بما فيها كلفة 99 bootstrap replicates.

## 6. بوابات القبول

لا يدخل أي مرشح المقارنة الموسعة إلا بعد:
- اختبارات رياضية مرجعية مستقلة للـ likelihood/recursion أو segmentation objective.
- تماثل اتجاه الكشف وعدم وجود تسرب مستقبلي.
- null وinjection على synthetic stress suite قبل البيانات الواقعية.
- قياس runtime؛ يمنع تشغيل 509×99 إذا كان التنفيذ المرجعي أبطأ من الحد التشغيلي أو يستهلك ذاكرة غير مضبوطة.
- تحقق مستقل على holdout دون تعديل thresholds بعد رؤية نتائجه.

لا دمج لمرشح لمجرد أن workflow نجح؛ النجاح الهندسي شرط لازم، وليس دليلاً على جودة الكشف.

## 7. مراجع خوارزمية

- FOCuS: Romano et al. (2023), *Fast Online Changepoint Detection via Functional Pruning CUSUM Statistics*, JMLR 24(81).
- R-FPOP: Fearnhead & Rigaill (2019), *Changepoint Detection in the Presence of Outliers*, JASA 114(525).
- BOCPD: Adams & MacKay (2007), *Bayesian Online Changepoint Detection*.
- Bartlett LRV: Bartlett-kernel HAC / Newey–West long-run variance estimator.

## 8. الحالة عند بدء هذه الدفعة

P2-B مدمج. نتائجها المرجعية: A_FAST حقق أعلى حساسية مع تأخير منخفض نسبياً لكنه احتفظ بإنذارات قبل onset؛ A_CONSENSUS أقل null/pre-onset لكنه أبطأ وأقل حساسية؛ Markov وParallel Fusion لم يثبتا توازناً مقبولاً. لذلك هدف P2-C هو تحسين trade-off بين الإنذار المبكر، الحساسية ثنائية الاتجاه، ومقاومة noise/outliers — لا إعادة معايرة أذرع P2-B الضعيفة.
