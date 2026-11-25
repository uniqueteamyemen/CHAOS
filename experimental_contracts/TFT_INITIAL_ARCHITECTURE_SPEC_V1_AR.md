# مواصفة البنية الأولية لـTFT — `macro_plus_eia_energy`

**الحالة: تصميم فقط.** هذه الوثيقة لا تنشئ نموذجاً، ولا تبني `TimeSeriesDataSet`، ولا تنفذ forward pass، ولا تشغّل تدريباً.

## 1. الغرض

هذه مواصفة أولية لكيفية تمثيل المصفوفة داخل Temporal Fusion Transformer بعد اعتماد العقد. الهدف هو منع الغموض قبل التنفيذ، لا اختيار أفضل hyperparameters بعد رؤية النتائج.

## 2. مخطط المدخلات

| الحقل | الاستخدام |
|---|---|
| `entity_code` | `group_id` وstatic categorical embedding للتعرف على الكيان؛ لا يُعامل كرقم ولا كترتيب جغرافي ولا كمتغير سببي |
| `year` | `time_idx` وترتيب زمني بنيوي؛ ليس متغيراً اقتصادياً مشتقاً |
| `wdi__NY.GDP.MKTP.KD.ZG` | target، وتاريخ الهدف السابق داخل encoder فقط |
| المتغيرات العشرة الأخرى | observed past covariates داخل encoder |
| المستقبل | لا توجد future-known exogenous covariates |

إدخال `entity_code` إلى طبقة static categorical لا يناقض منعه كميزة رقمية؛ فهو يحدد group/identity للنموذج. يجب تسجيل أثر هذا embedding منفصلاً لأن النموذج قد يتعلم فروقاً ثابتة بين الكيانات.

## 3. تمثيل الزمن

يستخدم كل كيان سنوات 2000–2024 بترتيب تصاعدي. عند origin `t`، تكون نافذة encoder هي `t-4..t`، ويكون target هو `t+1`. القيمة الفعلية للهدف في `t+1` تظهر أثناء التدريب كـlabel فقط، ولا تدخل كميزة في encoder. لا توجد أعمدة مستقبلية خارجية.

## 4. بنية TFT المقترحة

| المكوّن | الإعداد الأولي المقترح | سبب التحفظ |
|---|---:|---|
| نوع النموذج | Temporal Fusion Transformer، point forecast | يطابق عقد MAE/RMSE دون إضافة quantile contract الآن |
| target | `wdi__NY.GDP.MKTP.KD.ZG` | الهدف المعتمد مسبقاً |
| encoder length | 5 | العقد المعتمد |
| prediction length | 1 | سنة واحدة |
| hidden size | 16 | مناسب كبداية لمصفوفة صغيرة وعدد windows محدود |
| LSTM layers | 1 | تقليل التعقيد |
| attention heads | 2 | كافٍ للاستكشاف الأولي دون تضخيم البنية |
| hidden continuous size | 8 | مسار منخفض السعة للميزات المستمرة |
| dropout | 0.10 | regularization أولي، لا يُعد نتيجة نهائية |
| output | نقطة واحدة للسنة التالية | متسق مع MAE/RMSE الأساسية |
| loss | MAE-compatible point loss | لا يضيف quantile interpretation قبل عقد مستقل |
| static categorical | `entity_code` embedding | group identity فقط، لا feature رقمي |
| known future reals | لا يوجد | منع تسريب القيم المستقبلية |
| observed past reals | target history + 10 exogenous columns | كل القيم تاريخية مرصودة حتى origin |

هذه الإعدادات **initial design defaults** وليست نتيجة tuning. لا يجوز تعديلها بعد رؤية test؛ أي grid لاحق يجب أن يكون معلناً ومحصوراً ويستخدم train/validation فقط.

## 5. Dataset configuration المقترح للتنفيذ اللاحق

```text
Group IDs:
  entity_code

Time index:
  year

Target:
  wdi__NY.GDP.MKTP.KD.ZG

Observed past reals:
  wdi__NY.GDP.MKTP.KD.ZG
  wdi__NY.GDP.PCAP.KD
  wdi__FP.CPI.TOTL.ZG
  wdi__SP.POP.TOTL
  wdi__PA.NUS.PPP
  imf__NGDP_RPCH
  imf__PCPI
  imf__PPPEX
  imf__BCA_NGDPD
  eia__energy_consumption_per_capita
  eia__energy_consumption_per_gdp

Known future reals:
  none

Static categoricals:
  entity_code

Static reals:
  none

Encoder length:
  5

Prediction length:
  1
```

في أي إطار يحتاج target إلى حقل منفصل عن `time_varying_unknown_reals`، يُحفظ target في channel الهدف ويُسمح فقط بتاريخ target داخل encoder وفق semantics الإطار. لا يجوز تكرار target المستقبلية كـfeature.

## 6. التدريب والـcheckpoint — مواصفة مستقبلية فقط

عند اعتماد العقد لاحقاً، يمكن استخدام optimizer من نوع Adam، learning rate ابتدائي `1e-3`، batch size ابتدائي `64`، gradient clipping `0.1`، وearly stopping على `val_MAE`. هذه ليست أوامر تشغيل الآن، بل defaults يجب تثبيتها في سجل experiment قبل التنفيذ.

لا يُسمح باختيار checkpoint أو hyperparameters باستخدام test. المراقبة تكون على validation فقط، ثم يُستخدم test مرة نهائية بعد تجميد الإعداد.

## 7. Scaling وnormalization

العقد الحالي لا يعتمد أي scaling أو normalization. لذلك التصميم الأولي يجب أن يدعم raw-value mode، ويجب أن يفشل التنفيذ إذا احتاج الإطار إلى normalizer غير مُعلن. إذا تقرر لاحقاً استخدام scaling لأسباب عددية، فسيكون ذلك عقداً منفصلاً؛ ويُfit على train فقط، وتُحفظ parameters والـhash، ولا يُعاد تطبيقها على raw layer.

## 8. Baseline suite قبل TFT

قبل TFT في حملة مستقبلية، يُصمم ويُثبت دون رؤية test:

| baseline | الاستخدام |
|---|---|
| Persistence | المقارن الأساسي: target عند `t` يتنبأ بـ`t+1` |
| Entity train mean | متوسط كل كيان من train فقط |
| Global train mean | متوسط كل train فقط |
| Linear autoregressive | تاريخ الهدف المسموح فقط، مع مواصفة lag معلنة |
| Linear multivariate | اختياري، إذا اعتمدت مواصفته قبل النتائج |

لا تعني مقارنة TFT مع هذه النماذج إثبات causal structure.

## 9. التحقق قبل أول training run

يجب أن ينتج التنفيذ المستقبلي window manifest يحوي `experiment_id`, `entity_code`, `origin_year`, `encoder_years`, `target_year`, `split`, وhash البيانات والعقد. يجب أن يثبت هذا الملف عدم وجود duplicate windows وأن target year أكبر من آخر encoder year دائماً.

كما يجب تسجيل Python/framework versions، commit SHA، dataset SHA-256، config SHA-256، seeds، وقت التنفيذ، ومكان logs/checkpoints. لا يبدأ التدريب إذا فشل أي فحص.

## 10. حدود التفسير

Variable selection weights وattention وencoder timestep importance مؤشرات تمثيلية/تنبؤية فقط. لا تُسمى causal weights، ولا تُستخدم وحدها لترقية pattern. أي Reverse Extraction لاحق سيحتاج عقد أحداث منفصلاً وdiscovery/validation/holdout events، ولا يُضمّن داخل TFT baseline السنوي تلقائياً.

## القرار الحالي

**مسموح الآن:** مراجعة هذه المواصفة وتعديلها واعتمادها.

**غير مسموح الآن:** بناء النموذج، إنشاء windows تنفيذية، forward pass، fit، validation run، test run، stability grid، ablation، أو حقن أي شيء في `market-intelligence-engine`.
