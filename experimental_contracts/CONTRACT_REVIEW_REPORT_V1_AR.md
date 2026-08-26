# تقرير مراجعة Experimental Contract v1 قبل تصميم TFT

## النتيجة التنفيذية

تمت مراجعة `DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1.json` مقابل المصفوفة الخام الفعلية، ثم مقارنته بخطة الحملة المرفقة. اجتاز العقد التدقيق الآلي الحالي بالكامل: **3,500 صف، 140 كياناً، 25 سنة، 11 متغيراً، صفر خلايا مفقودة، صفر تكرارات entity-year، وترتيب زمني صحيح**. كما اجتازت حسابات النوافذ والتقسيم الزمني واختبارات temporal firewall.

هذا لا يعني أن TFT جاهز للتدريب فوراً. العقد يثبت **مواصفات البيانات والتقييم**، لكنه يحتاج قبل التدريب إلى تثبيت مواصفة البنية، نسخة الإطار البرمجي، seed policy، طريقة التعامل مع `entity_code` كمعرف مجموعة، وحسم موضوع target/input scaling. لذلك الخطوة المسموحة الآن هي تصميم البنية كمواصفة فقط، لا تشغيلها.

## 1. فحص المتطلبات الأساسية

| المتطلب | حالة العقد v1 | الحكم |
|---|---|---|
| Target | `wdi__NY.GDP.MKTP.KD.ZG` عند `t+1` | مطابق |
| Features | 11 أعمدة مصدرية؛ تاريخ الهدف داخل encoder فقط | مطابق، بشرط منع target المستقبلية |
| Entities | 140 من أصل 194 وفق اكتمال صارم | مطابق؛ `entity_code` معرف مجموعة وليس feature رقمياً |
| Period | 2000–2024 | مطابق |
| Native frequency | Annual | مطابق |
| Missing policy | لا imputation، ولا إعادة تصنيف للصفر | مطابق |
| Encoder | 5 سنوات `t-4..t` | مطابق |
| Horizon | سنة واحدة `t+1` | مطابق |
| Chronological split | Train 2006–2015، Validation 2016–2019، Test 2020–2024 | مطابق |
| Metrics | MAE/RMSE أساسيان؛ R² وdirectional accuracy ثانويان | مناسب؛ يُضاف global mean وAR إلى baseline suite لاحقاً |
| Baseline | Persistence أساسي وentity train mean ثانوي | مناسب، لكنه يحتاج توسيعاً قبل TFT وفق الخطة المرفقة |
| Leakage firewall | لا قيمة من `t+1` أو بعده داخل encoder | اجتاز التدقيق الآلي |

## 2. مراجعة التقسيم الزمني

التقسيم الحالي متسق حسابياً مع 140 كياناً:

| الجزء | سنوات الهدف | سنوات الأصل | عدد النوافذ |
|---|---|---|---:|
| Train | 2006–2015 | 2005–2014 | 1,400 |
| Validation | 2016–2019 | 2015–2018 | 560 |
| Test | 2020–2024 | 2019–2023 | 700 |
| الإجمالي | 2006–2024 | 2005–2023 | 2,660 |

لا يوجد تداخل زمني بين target years للأجزاء الثلاثة، ولا shuffle، ولا random entity split. نافذة الاختبار الأخيرة تستخدم 2019–2023 كمدخل وتستهدف 2020–2024 بالتتابع. يجب أن يثبت التنفيذ لاحقاً أن `target_year` لا يدخل في `encoder_years`، وأن validation/test لا يدخلان في fitting أو اختيار hyperparameters.

القيود المهمة هي أن 2000–2005 لا تنتج أهدافاً قابلة للتقييم في هذا العقد بسبب encoder بطول خمس سنوات، وهذا مقبول ومعلن، وليس فقداً يجب تعويضه. كذلك فإن الفترة 2020–2024 تتضمن صدمات تاريخية، لذلك يجب عرض metric كل سنة وتوزيع الأخطاء، لا متوسط test واحد فقط.

## 3. مراجعة المقاييس

اختيار MAE وRMSE مناسب لهدف نمو GDP الذي يقاس كنقاط مئوية وقد يساوي صفراً أو يغير إشارته. استبعاد MAPE صحيح لأن المقام قد يكون قريباً من الصفر أو يتغير مع الإشارة. يجب أن يكون MAE هو المقياس الأساسي للتفسير المباشر، وأن يستخدم RMSE لإظهار أثر الأخطاء الكبيرة.

يُضاف إلى العرض اللاحق، قبل TFT، **global train mean** و**linear autoregressive baseline**، كما تقترح الخطة المرفقة. ويجوز إضافة baseline خطي متعدد المتغيرات صغير، لكن يجب تثبيت مواصفته قبل رؤية validation/test results. لا تُستخدم أي baseline لإثبات causal structure.

يجب حساب المقاييس لاحقاً بثلاثة مستويات: pooled unweighted rows، وmedian/quantiles على مستوى الكيان، وجدول لكل سنة test. لا تستخدم أوزان السكان أو الناتج في headline metric. ويجب تثبيت تعريف directional accuracy، خصوصاً في حالة target يساوي صفراً؛ المقترح هو استبعاد الحالات التي يكون فيها كل من الحقيقة والتنبؤ على الصفر من بسط الاتجاه، وتسجيل قاعدة التعامل معها قبل التنفيذ.

## 4. ما أضافته الخطة المرفقة وما لا يدخل الآن

الخطة المرفقة مناسبة كخطة حملة لاحقة، لكنها ليست إذناً بتشغيل 48 ساعة الآن. ما يمكن اعتماده كمواصفات مستقبلية هو reproducibility lock، integrity/leakage audit، baseline suite، TFT baseline، stability grid، temporal robustness، ablations، reverse extraction، event holdout، surrogate gate، multiple testing، والـregistries.

أما الآن فلا تُشغّل مراحل التدريب أو stability أو ablation أو reverse extraction أو surrogate. Reverse Extraction يحتاج عقد أحداث منفصلاً، وevent holdout منفصلاً، ولا يجوز خلطه مع annual macro panel أو تحويل GED/GDELT إلى annual columns بلا عقد محاذاة خاص.

كما يجب ألا تُفسر variable-selection weights أو attention أو encoder timestep importance كسببية. أقصى ما تعطيه في هذه المرحلة هو وصف تمثيلي/تنبؤي يحتاج اختبار استقرار مستقل.

## 5. المتطلبات الإضافية قبل تصميم/تدريب TFT

قبل **التصميم القابل للتنفيذ** يجب تثبيت البنود التالية في مواصفة منفصلة:

| المتطلب | القرار المطلوب |
|---|---|
| Framework/version | تثبيت PyTorch وTFT framework وPython وإصدارات CUDA/CPU قبل التدريب |
| Entity handling | استخدام `entity_code` كـ`group_id` وstatic categorical embedding، مع منعه كرقم أو ترتيب جغرافي |
| Time index | `year` كـinteger time index داخل كل كيان، وليس feature اقتصادي إضافي |
| Covariate class | كل الأعمدة الـ11 observed historical covariates؛ لا future-known exogenous covariates |
| Decoder inputs | لا يُسمح بإدخال قيم مستقبلية غير متاحة؛ `time_idx` فقط كمعرفة زمنية بنيوية إذا تطلب الإطار ذلك |
| Scaling | العقد الحالي لا يعتمد أي scaling؛ يجب إما تثبيت raw-value mode أو اعتماد scaler منفصل fit على train فقط بعقد جديد |
| Seeds | قائمة seeds ثابتة قبل التدريب، لا seed واحد مخفي |
| Window audit | إنشاء جدول windows يحوي entity، origin، encoder years، target year، split، والتحقق من duplicate windows |
| Baseline suite | persistence، entity train mean، global train mean، AR، ثم baseline خطي متعدد المتغيرات إن اعتمد قبل النتائج |
| Checkpoint rule | اختيار checkpoint وearly stopping من train/validation فقط؛ test مرة نهائية بعد تثبيت الإعداد |
| Logging | experiment_id، commit SHA، dataset hash، config hash، seed، model version، timestamp |

أهم نقطة تحتاج قراراً قبل التدريب هي **scaling**. عدم التطبيع يحافظ على الخام، لكنه يجعل population وPPP وGDP per capita وEIA intensity مختلفة جداً في المقياس. لا يجوز حل ذلك تلقائياً؛ إما يبقى raw-value baseline كما هو، أو يُعتمد target/input scaling كتحويل مشتق fit على train فقط في عقد منفصل.

## 6. قرار تصميم البنية الأولية المسموح الآن

يسمح العقد بتصميم TFT أولي بالمواصفات التالية دون تشغيل:

```text
TFT architecture specification only

Group IDs: entity_code
Static categorical: entity_code embedding, used for identity/grouping only
Time index: year
Observed past reals: the 11 selected columns
Known future reals: none, except structural time index if framework requires it
Encoder length: 5
Prediction length: 1
Target: wdi__NY.GDP.MKTP.KD.ZG at t+1
Loss proposal: MAE-compatible point loss or explicitly reviewed quantile loss
Normalizer: none in current raw contract; scaling requires separate approval
Attention/importance: descriptive only, never causal evidence
```

لا يعني ذلك أن بناء `TimeSeriesDataSet` أو `TemporalFusionTransformer` أو تشغيل forward pass قد تم. التصميم المسموح الآن هو schema/configuration review فقط.

## 7. الملفات والـaudit

تم حفظ هذا التقرير وملف التدقيق الآلي في CHAOS. ملف التدقيق هو `CONTRACT_REVIEW_AUDIT_V1.json`، ويحتوي SHA-256 للعقد والمصفوفة ونتيجة كل فحص. لم يُشغّل أي نموذج أو تدريب.

**الخلاصة:** العقد يفي بمتطلبات target/features/entities/period/frequency/missing policy/encoder/horizon/split/metrics/baseline على مستوى Data Contract. توجد متطلبات إضافية قبل التدريب، أهمها architecture schema، versions/seeds، window registry، expanded baseline suite، وقاعدة scaling. يمكن الانتقال الآن إلى **تصميم بنية TFT الأولية كمواصفة تنفيذية فقط**، ثم التوقف للمراجعة قبل أي training.
