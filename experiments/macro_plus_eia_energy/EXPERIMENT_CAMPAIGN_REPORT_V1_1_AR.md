# تقرير الحملة التجريبية — `macro_plus_eia_energy` TFT v1.1

## الحالة التنفيذية

اكتملت الحملة الأولية المسموح بها: تدقيق العقد، integrity/leakage audit، إصلاح فشل الاكتمال الرقمي، reproducibility lock، baseline suite، تدريب TFT، التقييم، وحفظ المخرجات. لم تُشغّل stability grid أو ablation campaign أو reverse extraction أو surrogate validation، ولم يُعدّل raw data أو `market-intelligence-engine` أو production architecture.

> النتيجة الحالية **baseline تنبؤية أولية** وليست دليلاً على السببية، وليست نمطاً بنيوياً معتمداً، وليست إذناً بحقن النموذج في المنصة.

## 1. العقد والبيانات

بدأ العقد بنسخة v1 التي أعلنت 140 كياناً. كشف أول تشغيل فعلي أن ست خلايا EIA كانت marker نصياً `--` للكيان SRB في 2000–2005؛ لذلك لم تُستبدل القيم ولم تُعبأ. أُعيد فحص الـ194 كياناً باستخدام numeric coercion فقط، فنتجت نسخة v1.1 محافظة تضم **139 كياناً** مكتملة رقمياً عبر 11 متغيراً و25 سنة.

| البند | الإعداد النهائي v1.1 |
|---|---:|
| الفترة | 2000–2024 |
| التواتر | سنوي أصلي |
| الكيانات | 139 |
| الصفوف | 3,475 |
| المتغيرات | 11 |
| الخلايا المفقودة/غير الرقمية داخل النسخة النهائية | 0 |
| raw layer | لم تُعدّل |
| قاعدة الفجوات | لا imputation ولا تحويل marker إلى قيمة |

المصفوفة النهائية هي [`MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv`](../../catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv). وتبقى النسخ السابقة وسجلات الفشل محفوظة للمراجعة، ولا تمثل نتائج التدريب النهائي.

## 2. الهدف والميزات

الهدف هو `wdi__NY.GDP.MKTP.KD.ZG` عند `t+1`، أي نمو الناتج المحلي الإجمالي السنوي الخام. تضم المصفوفة تاريخ الهدف السابق داخل encoder، وأربعة متغيرات WDI إضافية، وأربعة متغيرات IMF، ومفهومي EIA للطاقة. استُخدمت aliases مشتقة آمنة داخل مكتبة TFT لأن أسماء WDI الأصلية تحتوي نقاطاً؛ يحفظ سجل التجربة mapping إلى المعرفات الأصلية، ولا يغير ذلك raw data.

جميع المتغيرات دخلت كـobserved past reals. لم توجد future-known exogenous covariates، ولم تُستخدم قيم مستقبلية داخل encoder. استُخدم `entity_code` كـgroup identifier وstatic categorical embedding فقط، وليس كمتغير رقمي أو ترتيب جغرافي.

## 3. التدقيق والتقسيم

اجتازت النسخة v1.1 كل فحوصات integrity/leakage:

| الفحص | النتيجة |
|---|---:|
| صفوف المصفوفة | 3,475 |
| الكيانات | 139 |
| المتغيرات | 11 |
| الخلايا المفقودة بعد numeric validation | 0 |
| تكرار entity-year | 0 |
| تكرار windows | 0 |
| خروقات target داخل encoder | 0 |
| خروقات وجود encoder/target | 0 |
| الترتيب الزمني | ناجح |

استخدمت النوافذ encoder بطول 5 سنوات وأفقاً سنة واحدة:

| الجزء | سنوات الهدف | سنوات الأصل | النوافذ |
|---|---|---|---:|
| Train | 2006–2015 | 2005–2014 | 1,390 |
| Validation | 2016–2019 | 2015–2018 | 556 |
| Test | 2020–2024 | 2019–2023 | 695 |
| الإجمالي | 2006–2024 | 2005–2023 | 2,641 |

التقسيم زمني، دون shuffle أو random entity split. اختير checkpoint من validation فقط، ثم قُيّم الاختبار مرة مقفلة بعد تجميد الإعداد.

## 4. البيئة وقابلية الإعادة

سُجلت البيئة في reproducibility lock: Python 3.12.3، PyTorch 2.13.0، Lightning 2.6.5، PyTorch Forecasting 1.8.0، pandas 2.3.3، وNumPy 2.3.5. استُخدم seed أساسي 17. وحُفظت hashes للعقد v1.1، architecture spec، المصفوفة، وpreflight audit.

استُخدم raw-value mode صراحة: `target_normalizer=None` و`scalers={feature: None}` لمنع auto-scaling داخل `TimeSeriesDataSet`. لم يُستخدم log أو difference أو normalization أو z-score أو imputation.

## 5. Baseline suite

شُغلت أربعة baselines قبل TFT باستخدام train-only fitting حيث يلزم:

| baseline | Test MAE | Test RMSE | Test R² | Directional accuracy |
|---|---:|---:|---:|---:|
| Global train mean | 4.0679 | 6.8142 | -0.0211 | 0.7755 |
| Entity train mean | 4.2962 | 6.9512 | -0.0626 | 0.7597 |
| Persistence one-step | 5.7012 | 9.1105 | -0.8253 | 0.6345 |
| Linear AR(5) per entity | 6.0327 | 9.4328 | -0.9567 | 0.6906 |

لم يُشغّل raw multivariate linear baseline لأن كل كيان يملك 10 نوافذ تدريب فقط مقابل 11 عموداً، ما يجعل النموذج غير محدد من دون regularization أو scaling بعقد منفصل. لا يمثل ذلك فشلاً في البيانات، بل قراراً منهجياً لمنع baseline غير صالح.

## 6. TFT baseline

استخدم TFT بإعداد أولي منخفض السعة: hidden size 16، طبقة LSTM واحدة، رأسان للـattention، hidden continuous size 8، dropout 0.10، learning rate `1e-3`، batch size 64، gradient clip 0.1، وearly stopping على `val_loss` مع patience 8. هذه إعدادات baseline واحدة وليست stability grid.

| split | MAE | RMSE | R² | Directional accuracy |
|---|---:|---:|---:|---:|
| Validation، 556 نافذة | 1.6014 | 2.5955 | 0.1879 | 0.9227 |
| Test، 695 نافذة | 3.9360 | 6.6332 | 0.0324 | 0.7741 |

على test، حسّن TFT على أفضل baseline وهو global train mean بمقدار **0.1319 MAE**، أي نحو **3.24%**، وبمقدار **0.1810 RMSE**، أي نحو **2.66%**. ارتفع R² من -0.0211 إلى 0.0324. لكن directional accuracy انخفضت قليلاً من 0.7755 إلى 0.7741؛ لذلك لا يصح وصف TFT بأنه أفضل في كل مقياس.

توزيع MAE على مستوى الكيان في test كان: median **3.0395**، الربع الأول **2.1741**، الربع الثالث **4.6645**، الأدنى **0.8029**، والأعلى **35.6033**. توجد 25 كيانات بأخطاء MAE أكبر من 5، وهو تذكير بأن المتوسط المجمع يخفي تفاوتاً كبيراً بين الكيانات.

## 7. الفشل والإصلاحات

حدثت عدة إخفاقات تنفيذية وتم إصلاحها وتوثيقها. رفضت مكتبة TFT معرفات WDI التي تحتوي نقاطاً، فاستُخدمت aliases مشتقة. فشل استخدام TorchNormalizer داخل `scalers` مع DataFrame، فتم اعتماد raw-value configuration صريحة. ظهر assertion لأن target دخل في scalers، فاستُبعد من القاموس. ثم كشف التشغيل marker `--` الذي أخفاه الفحص الأول؛ أُنشئت v1.1 باستبعاد الكيانات غير الرقمية دون أي تعويض. وأخيراً صُحح استخراج Prediction object وتسمية target year.

هذه الإصلاحات محفوظة في [`EXECUTION_FAILURE_AND_REPAIR_LOG_AR.md`](EXECUTION_FAILURE_AND_REPAIR_LOG_AR.md)، ولا توجد محاولة فاشلة مخفية من التقرير.

## 8. ما الذي تعلمه النموذج وما الذي لم يثبته

أظهر TFT قيمة تنبؤية أولية أفضل قليلاً من أفضل baseline في MAE وRMSE وR² على test ضمن هذا التقسيم. هذا يبرر اعتباره **مرشح baseline مفيداً للتحليل اللاحق**، لا نموذجاً مستقراً أو نمطاً مكتشفاً نهائياً.

لم يثبت التدريب أن أي متغير سببي، ولم يثبت أن attention أو variable-selection weights تمثل أسباباً. كما لم يُختبر الاستقرار عبر seeds أو أطوال encoder أو العصور الزمنية، ولم تُنفذ ablations لتحديد مقدار مساهمة WDI أو IMF أو EIA، ولم يُنفذ Reverse Extraction على أحداث تاريخية.

## 9. ما لم يُنفذ

لم تُشغّل stability grid، ولم تُشغّل temporal robustness، ولم تُنفذ variable-selection report مستقلة، ولا ablations، ولا target-history ablation، ولا lag pattern registry، ولا Reverse Extraction، ولا event holdout، ولا surrogate validation، ولا multiple-testing campaign. هذه مراحل لاحقة تحتاج contracts محددة ولا يجوز استنتاجها من نتيجة هذا baseline.

## 10. الملفات الرئيسية

| الملف | الوظيفة |
|---|---|
| [`TFT_TRAINING_SUMMARY.json`](TFT_TRAINING_SUMMARY.json) | ملخص checkpoint والاختبار |
| [`TFT_TEST_METRICS.json`](TFT_TEST_METRICS.json) | المقاييس النهائية للاختبار |
| [`TFT_TEST_PREDICTIONS.csv`](TFT_TEST_PREDICTIONS.csv) | التنبؤات والبواقي لكل نافذة test |
| [`TFT_TEST_PER_ENTITY_METRICS.csv`](TFT_TEST_PER_ENTITY_METRICS.csv) | أخطاء كل كيان |
| [`TFT_VALIDATION_PREDICTIONS.csv`](TFT_VALIDATION_PREDICTIONS.csv) | تنبؤات validation |
| [`TFT_VALIDATION_PER_ENTITY_METRICS.csv`](TFT_VALIDATION_PER_ENTITY_METRICS.csv) | أخطاء validation لكل كيان |
| [`MODEL_BASELINE_COMPARISON_V1_1.csv`](MODEL_BASELINE_COMPARISON_V1_1.csv) | مقارنة TFT وbaselines |
| [`TFT_RESULT_SUMMARY_V1_1.json`](TFT_RESULT_SUMMARY_V1_1.json) | فروق الأداء والتوزيعات |
| [`REPRODUCIBILITY_LOCK.json`](REPRODUCIBILITY_LOCK.json) | البيئة والhashes والseed |
| [`PRE_TRAIN_INTEGRITY_LEAKAGE_AUDIT_V1_1.json`](../../experimental_contracts/PRE_TRAIN_INTEGRITY_LEAKAGE_AUDIT_V1_1.json) | بوابة ما قبل التدريب |

## الخلاصة

نجح أول TFT baseline بعد تصحيح فشل data-readiness الحقيقي. النتيجة واعدة بدرجة محدودة: أفضل من baselines في MAE/RMSE/R² على test، لكنها لا تزال نتيجة single-seed/single-configuration على panel سنوي صغير نسبياً، مع تفاوت كبير بين الكيانات. لذلك تُسجل النتيجة في CHAOS كـ**exploratory predictive baseline**، ولا تُرقى إلى candidate structural pattern ولا تُحقن في المنصة قبل stability وablation وhistorical replay وReverse Extraction المناسبة.

## المراجع الداخلية

[1]: ../../experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1_1.json "Contract v1.1"
[2]: ../../experimental_contracts/PRE_TRAIN_INTEGRITY_LEAKAGE_AUDIT_V1_1.json "Pre-train integrity and leakage audit v1.1"
[3]: BASELINE_V1_1_METRICS.csv "Baseline metrics v1.1"
[4]: MODEL_BASELINE_COMPARISON_V1_1.csv "TFT and baseline comparison v1.1"
[5]: TFT_RESULT_SUMMARY_V1_1.json "TFT result summary v1.1"
