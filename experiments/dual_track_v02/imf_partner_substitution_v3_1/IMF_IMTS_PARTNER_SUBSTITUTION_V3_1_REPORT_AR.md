# تقرير تشغيل عقد IMF IMTS Partner Substitution V3.1

## الحكم التنفيذي

شُغّل عقد V3.1 بعد التحقق من hash العقد المجمد. النتيجة النهائية هي **`not_testable`**، وليست `supported_predictive`. لم يُفتح مسار Causal Validation، ولم تُمنح النتيجة أي positive Composer أو runtime weight.

السبب ليس غياب الإشارة الوصفية بالكامل، بل فشل المرشح في الاختبار الذي طلبه العقد: لم يتفوق على simple rank-autocorrelation baseline، وفشل شرط حجم الأثر، وفشل شرط التغطية في النوافذ الفرعية، كما أن nulls الأقوى لم تدعم أفضلية المرشح.

## تعريف الاختبار

عرّف العقد الصدمة بأنها خروج baseline top-1: يكون الشريك الأساسي top-1 في السنة السابقة، ثم يصبح شريك آخر top-1 في سنة الحدث داخل candidate pool الثابتة ذات العشرة شركاء. عرّف المرشح الشريك البديل الأعلى رتبة بين الشركاء غير الأساسيين الذين ظهروا في top-3 خلال السنتين السابقتين. الناتج هو مطابقة البديل المرشح للـtop-1 الفعلي واستمراره top-1 لمدة h=1 أو 2 أو 3 سنوات.

استخدم التشغيل 135 reporter، مع baseline selection في 2000–2004، وfit في 2005–2014، وconfirmation مقفلة في 2015–2024. لم تُستخدم outcomes لإعادة الاختيار، ولم تطبق imputation أو missing-as-zero أو normalization أو log أو differencing أو smoothing أو frequency conversion.

## نتائج confirmation

| الأفق | الأحداث | reporters | candidate rate | rank baseline rate | lift candidate−rank | candidate Brier | rank Brier |
|---:|---:|---:|---:|---:|---:|---:|---:|
| h=1 | 42 | 34 | 0.5238 | 0.5476 | -0.0238 | 0.2166 | 0.2482 |
| h=2 | 42 | 34 | 0.3571 | 0.3810 | -0.0238 | 0.2141 | 0.2406 |
| h=3 | 42 | 34 | 0.2857 | 0.3095 | -0.0238 | 0.1953 | 0.2180 |

يوجد تحسن عددي في Brier مقابل rank baseline، لكنه `0.0265` عند h=2 فقط، وهو أقل من الحد المجمد `0.05`. أما معدلات النجاح الدقيقة فكانت أسوأ للمرشح عند كل الآفاق. baseline السابق للشريك القديم أعطى نجاحاً صفرياً ميكانيكياً لأن الحدث عُرّف أصلاً على أنه خروج ذلك الشريك؛ سُجل ولم يُخفَ، لكنه ليس خطاً أساسياً صالحاً لتبرير ترقية المرشح.

## النوافذ الفرعية والاستبعاد المؤثر

عند h=2، كان عدد الأحداث في النوافذ الفرعية الثلاث `11` و`18` و`14`، بينما يشترط العقد 30 حدثاً في كل نافذة. لذلك فاختبار الاستقرار الزمني **غير قابل للحكم** (`not_testable`) حتى قبل محاولة تفسير اتجاهه. كانت lift في النافذة الأولى `-0.0909` ثم `0.0` و`0.0` في النافذتين التاليتين.

حُددت الدول الثلاث الأعلى مساهمة في fit قبل قراءة confirmation: `ETH`, `MDV`, `MWI`. بعد استبعادها بقي lift عند h=2 سالباً، `-0.02564`، ولذلك لم يكن الحكم ناتجاً عن دولة مؤثرة واحدة. وكان تركّز confirmation ضمن الحد؛ لم تتجاوز مساهمة reporter واحدة 5% من أحداث confirmation.

## null controls وFDR/Holm

| null | h=2 raw p | Holm-adjusted p | unique statistics | القرار |
|---|---:|---:|---:|---|
| block permutation داخل reporter | 0.3085 | 0.9254 | 148 | لا يثبت أفضلية |
| rank-preserving volume-constrained | 0.9999 | 1.0000 | 93 | يفشل بوضوح |
| restricted time placebo | 1.0000 | 1.0000 | 21 | placebo أفضل من المرشح |

كل null كان non-degenerate. استُخدم Holm-Bonferroni على عائلة المقارنات الثلاث عند `alpha=0.025`. لم ينجح أي null-adjusted comparison في بوابة العقد، ولم يكن هناك أي p-value صالح للترقية.

## Stability والحوكمة

أعيد التشغيل عبر seeds `271108–271112`. بقيت معدلات النجاح وlift سالبة بالاتجاه نفسه عبر seeds؛ Stability Grid سجلت `stable_negative_primary_lift`. لا يغير اختلاف seed قراراً حتمياً سلبياً أصلاً.

سُجلت TransitionEvidence V3.1 كـ`not_testable`، وسُجلت كل أسباب الفشل في exclusion/ledger artifacts. لا توجد دعوى سببية. بقي `causal_validation_status=not_run` و`runtime_status=not_eligible`. سيُضاف السجل إلى Evidence Graph مع قواعد الاستبعاد نفسها: لا يدخل `not_testable` في positive composition.

## القرار

تُغلق V3.1 كاختبار غير قابل للترقية، ولا تُعاد إعادة tuning لنفس السؤال. إذا استمر البحث مستقبلاً، فالمشكلة المنهجية الأولى التي يجب معالجتها ليست threshold، بل تصميم baseline/event universe: naive previous-partner يصبح degenerate عندما تكون الصدمة معرفة بخروجه، والنوافذ القصيرة لا توفر 30 حدثاً. أي عقد جديد يجب أن يغير السؤال أو يعيد تعريف event universe قبل تجميده، لا أن يعيد تشغيل V3.1 بعدياً.
