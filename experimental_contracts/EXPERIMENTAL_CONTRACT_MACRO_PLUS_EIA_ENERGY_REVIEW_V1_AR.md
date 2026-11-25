# عقد التجربة الأولية — `macro_plus_eia_energy`

**الحالة: مسودة مراجعة قبل التدريب.** لا يُشغّل TFT أو أي تدريب أو structure-learning أو surrogate قبل اعتماد هذا العقد صراحة.

هذا العقد يصف تجربة تنبؤية أولية على بيانات تاريخية سنوية. نجاحها أو فشلها لا يثبت السببية، ولا يثبت أن النموذج استعاد البنية الحقيقية، ولا يسمح تلقائياً بحقن أي نتيجة في `market-intelligence-engine`.

## 1. Dataset Configuration

| البند | الإعداد المعتمد للمراجعة |
|---|---|
| المصفوفة | `macro_plus_eia_energy` |
| التواتر الأصلي | سنوي لكل الأعمدة الإحدى عشرة |
| الفترة الخام | 2000–2024، 25 سنة |
| مفتاح الكيان | `entity_code` المصدرّي |
| معنى الكيان | اقتصاد/كيان إحصائي كما يرد في WDI/IMF/EIA؛ لا يُعامل كرقم ولا كميزة مرتبة |
| الكون الكامل | 194 كياناً، محفوظ مع فجواته |
| كون التجربة | 140 كياناً اجتاز شرط الاكتمال الصارم |
| صفوف panel الخام للتجربة | 3,500 صف، 140 × 25 |
| خلايا المتغيرات | 38,500 خلية، 11 × 140 × 25 |
| الخلايا المفقودة داخل نسخة الـ140 | صفر؛ بسبب الاختيار الصارم، وليس بسبب تعبئة أو تقدير |

الملف الخام الأساسي هو `catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_140_RAW_2000_2024_WIDE.csv`. وتبقى نسخة الـ194 وملف فجواتها محفوظين للمراجعة، ولا تُدمج تلقائياً في هذه التجربة.

## 2. Target

الهدف الأساسي هو:

```text
wdi__NY.GDP.MKTP.KD.ZG
```

وهو **النمو السنوي للناتج المحلي الإجمالي** وفق WDI، بوحدة النسبة المئوية وعلى أساس constant 2015 US$. لا يُعاد اشتقاقه ولا يُعاد حسابه من GDP levels.

صيغة الهدف عند سنة الأصل `t` هي:

```text
target(entity, t+1) = wdi__NY.GDP.MKTP.KD.ZG(entity, t+1)
```

أي أن التجربة تتنبأ بقيمة النمو الخام للسنة التالية، لا باتجاه مصطنع ولا بتغير مشتق جديد.

## 3. Features

تتكون المجموعة من **11 عموداً مصدرّياً**. يظهر الهدف داخل نافذة التاريخ السابقة فقط، وليس كقيمة مستقبلية:

| المتغير | المصدر | الدور | الوحدة أو التعريف |
|---|---|---|---|
| `wdi__NY.GDP.MKTP.KD.ZG` | WDI | تاريخ الهدف داخل encoder فقط | GDP annual growth، % |
| `wdi__NY.GDP.PCAP.KD` | WDI | متغير اقتصادي زمني | GDP per capita، constant 2015 US$ |
| `wdi__FP.CPI.TOTL.ZG` | WDI | متغير أسعار | CPI annual growth، % |
| `wdi__SP.POP.TOTL` | WDI | متغير سكاني | midyear population، persons |
| `wdi__PA.NUS.PPP` | WDI | متغير مقارنة سعرية | LCU per international dollar |
| `imf__NGDP_RPCH` | IMF WEO | متغير نمو/مقارنة مصدرية | IMF real GDP growth، % |
| `imf__PCPI` | IMF WEO | متغير مقارنة سعرية مصدرية | source-defined annual CPI index؛ ليس مفترضاً أنه نسبة تضخم في هذه النسخة |
| `imf__PPPEX` | IMF WEO | متغير مقارنة سعرية | source-defined PPP exchange rate |
| `imf__BCA_NGDPD` | IMF WEO | متغير خارجي | current-account balance، % of GDP |
| `eia__energy_consumption_per_capita` | EIA | متغير طاقة | million Btu per person |
| `eia__energy_consumption_per_gdp` | EIA | كثافة طاقة | thousand Btu per USD at PPP |

تبقى WDI وIMF وEIA أعمدة منفصلة. لا يوجد متوسط أو reconciliation بين WDI وIMF، ولا يعاد حساب EIA من WDI أو IMF.

## 4. الدول/الكيانات

يستخدم العقد 140 كياناً مكتملة القيم عبر كل المتغيرات والسنوات. القائمة ليست حكماً سياسياً على ماهية الكيان؛ هي نتيجة شرط data-readiness مطبق على `entity_code` المصدرّي. لا يدخل `entity_code` كميزة عددية، ولا تُمنح الكيانات أوزاناً بسبب الاسم أو الموقع.

## 5. Missing-data policy

السياسة هي **عدم التعبئة مطلقاً**:

| العملية | القرار |
|---|---|
| Forward-fill | ممنوع |
| Backward-fill | ممنوع |
| Interpolation | ممنوع |
| Mean/median fill | ممنوع |
| إعادة تصنيف الصفر كفراغ أو العكس | ممنوع |
| إسقاط متغير بعد رؤية النتائج | ممنوع |
| إصلاح تلقائي أثناء بناء النوافذ | ممنوع؛ يفشل التشغيل مع تقرير واضح |

كون الـ140 بلا فراغات لا يعني أن المصادر بلا فجوات عامة. النسخة الكاملة من 194 كياناً تحتوي 1,490 خلية مفقودة من أصل 53,350، وتظل محفوظة كطبقة فحص منفصلة.

## 6. Transformations

لا توجد أي عملية تحويل معتمدة في هذه المسودة. لا log، ولا differencing، ولا returns، ولا z-score، ولا normalization، ولا winsorization، ولا clipping، ولا تحويل عملات، ولا source reconciliation. كما أن target scaling داخل TFT **غير معتمد**؛ إذا ظهر احتياج إليه لاحقاً، فيلزم تعديل عقد مستقل ويجب أن يُfit على train فقط.

## 7. Encoder وPrediction Horizon

| البند | الإعداد |
|---|---:|
| `encoder_length` | 5 سنوات |
| نافذة الإدخال عند الأصل `t` | `t-4` إلى `t` |
| `prediction_length` | سنة واحدة |
| الهدف | `t+1` |
| Future-known covariates | لا يوجد |
| إعادة بناء release dates | لا؛ هذه latest-vintage historical replay |
| قاعدة التسريب | لا تدخل أي قيمة من `t+1` أو بعده في نافذة الأصل `t` |

إعادة بناء المعلومات التي كانت متاحة لحظة الإصدار ليست جزءاً من هذا baseline؛ ولذلك يجب وصف النتيجة لاحقاً بأنها latest-vintage replay، لا real-time replay.

## 8. Chronological Train/Validation/Test Split

| الجزء | سنوات الهدف | سنوات الأصل `t` | عدد النوافذ المتوقع |
|---|---|---|---:|
| Train | 2006–2015 | 2005–2014 | 1,400 |
| Validation | 2016–2019 | 2015–2018 | 560 |
| Test | 2020–2024 | 2019–2023 | 700 |
| الإجمالي | 2006–2024 | 2005–2023 | 2,660 |

التقسيم زمني صارم. لا shuffle، ولا random entity split، ولا استخدام للاختبار في اختيار hyperparameters أو early stopping.

## 9. Metrics

المقاييس الأساسية هي **MAE** و**RMSE**. ويجوز عرض `R² out-of-sample` و`directional accuracy` كمقاييس ثانوية وصفية. يمكن عرض sMAPE بحذر، لكن MAPE ليس مقياساً أساسياً لأن نمو GDP قد يساوي صفراً أو يغير إشارته.

تُعرض النتائج بطريقتين: pooled unweighted row-level metrics، وتوزيع الأخطاء على مستوى الكيان. لا تُستخدم أوزان السكان أو الناتج في الرقم الرئيسي، ولا يُسمح لمتوسط واحد بإخفاء فشل كيانات محددة.

## 10. Baseline المقارن

الـbaseline الرئيسي هو **one-step persistence**:

```text
prediction(entity, t+1) = raw target(entity, t)
```

ويُسمح بbaseline ثانوي هو متوسط الهدف لكل كيان محسوب من سنوات train فقط. لا يُحسب أي baseline من كامل التاريخ قبل التقسيم.

لا تُعد TFT متفوقة إلا إذا حسنت على persistence في MAE وRMSE على test، مع تقرير توزيع الأخطاء. وحتى عند تحقق ذلك، فهذا أداء تنبؤي وليس دليلاً على السببية أو على استعادة «القانون» الحقيقي.

## 11. بوابة الاعتماد

قبل التدريب يجب اعتماد: الهدف، المتغيرات الإحدى عشرة، الـ140 كياناً، الفترة، التواتر السنوي، encoder بطول 5، أفق سنة، التقسيم الزمني، سياسة عدم التعبئة، منع التحويلات، metrics، وbaseline persistence.

**الحالة الحالية:** العقد جاهز للمراجعة فقط. لم يُشغّل TFT، ولم يُشغّل أي تدريب، ولم تُعدّل البيانات الخام أو architecture أو `market-intelligence-engine`.

## الملفات

| الملف | الدور |
|---|---|
| `experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1.json` | إعداد آلي قابل للتحقق |
| `experimental_contracts/EXPERIMENTAL_CONTRACT_MACRO_PLUS_EIA_ENERGY_REVIEW_V1_AR.md` | نسخة المراجعة العربية |
| `catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_140_RAW_2000_2024_WIDE.csv` | المصفوفة الخام المختارة |
| `catalog_first/readiness_gate/macro_plus_eia_energy/SELECTED_VARIABLE_PROVENANCE.csv` | provenance للمتغيرات الإحدى عشرة |
