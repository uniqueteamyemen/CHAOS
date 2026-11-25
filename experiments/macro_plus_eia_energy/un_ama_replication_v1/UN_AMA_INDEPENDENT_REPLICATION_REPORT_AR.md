# تقرير Independent Replication على UN AMA

## الخلاصة التنفيذية

اختبرت صيغة `high current growth` على مصدر مستقل فعلي هو **UN Statistics Division National Accounts Main Aggregates (AMA)**، بدلاً من إعادة استخدام `macro_plus_eia_energy`. استُخدم ملف AMA الرسمي المرفوع في يناير 2026، واستُخرجت منه سلسلة `Gross Domestic Product (GDP)` عند الأسعار الثابتة 2020، إضافة إلى صف `Population`، مع إبقاء ملفي Excel الخام كما هما.

الصيغة كانت مجمدة قبل قراءة نتائج AMA:

```text
ama_gdp_growth_pct[t] > 4.0
→ ama_gdp_growth_pct[t+3] <= ama_gdp_growth_pct[t] - 2 percentage points
```

النتيجة مشجعة: حققت القاعدة في validation Balanced Accuracy=`0.7325` وF1=`0.6185`، ثم بقيت فوق BA العشوائي في confirmation عند BA=`0.6821` وF1=`0.5038`. وفي كلا الجزأين كان p مقابل label permutation داخل الدولة، مع قاعدة مجمدة، أقل من الحد الأدنى المحسوب من 2,000 تكرار (`p=0.0005`).

هذه **إشارة تكرار مستقلة أولية** وليست إثباتاً نهائياً لنمط عام. السبب أن المصدر المستقل يعيد تعريف الناتج نفسه بطريقة AMA، وبعض سلاسل AMA قد تتضمن تقديرات عند غياب البيانات الرسمية، كما أن القاعدة ما زالت تعتمد نمو الناتج الحالي وحده ولا تتضمن مساراً سببياً أو عقدة ثانية مثبتة.

## المصدر والبيانات

صفحة التنزيل الرسمية في [UN AMA Downloads][1] تعلن أن قاعدة National Accounts Main Aggregates تُحدّث سنوياً، وتوفر ملف Growth Rate of GDP وملف Exchange Rates and Population. الصفحة الرئيسية للقاعدة تذكر أن التغطية تمتد من 1970 لأكثر من 200 دولة/منطقة، وأن بعض السلاسل قد تستخدم إجراءات تقدير عند غياب مجموعة كاملة من البيانات الرسمية.[2]

| العنصر | القيمة الفعلية |
|---|---|
| Growth file | `AMA_GDP_GROWTH_ALL_COUNTRIES_RAW.xlsx` |
| Population file | `AMA_EXCHANGE_RATES_POPULATION_ALL_COUNTRIES_RAW.xlsx` |
| AMA upload | January 2026 |
| Growth indicator | `Gross Domestic Product (GDP)` |
| Frequency | Annual |
| Raw coverage | 1970–2024 |
| Countries in derived panel | 220 CountryID |
| Derived rows | 12,100 |
| Raw transformation | لا تعديل |
| Staging selection | صف GDP وصف Population فقط |
| Imputation | لا |
| Normalization | لا |
| Source averaging | لا |

للمقارنة، اختُبرت replication على السنوات التي تنتهي في 2019 فقط. استُبعدت 2020–2024 عمداً لأنها كانت نافذة locked test في عقد CHAOS السابق، رغم وجودها في ملف AMA.

## العقد المجمد

| البعد | التعريف |
|---|---|
| Rule | `ama_gdp_growth_pct[t] > 4.0` |
| Outcome family | `material_drop_2pp` |
| Outcome | `ama_gdp_growth_pct[t+3] <= ama_gdp_growth_pct[t] - 2.0` |
| Horizon | 3 سنوات |
| Discovery fit | target years 2003–2009 |
| Discovery inner | 2010–2012 |
| Validation | 2013–2016 |
| Confirmation | 2017–2019 |
| Excluded future | 2020–2024 |
| Selection after metrics | ممنوع ولم يحدث |

لم تُستخدم population في قاعدة replication نفسها؛ وجودها في اللوحة محفوظ للفحص الوصفي فقط. وهذا متعمد، لأن locked test السابق أظهر أن population وenergy-per-GDP لم يضيفا قيمة مستقلة فوق high growth. السؤال الحالي هو: هل **النواة high-growth → material deterioration** تنتقل إلى source مستقل؟

## النتائج حسب الجزء الزمني

| Split | Origins | Countries | Positive outcomes | Support | Precision | Recall | F1 | Balanced Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery fit | 1,472 | 212 | 440 | 793 | 0.4313 | 0.7773 | 0.5547 | 0.6701 |
| Discovery inner | 636 | 214 | 191 | 296 | 0.5068 | 0.7853 | 0.6160 | 0.7286 |
| Validation | 848 | 212 | 253 | 397 | 0.5063 | 0.7945 | 0.6185 | **0.7325** |
| Confirmation | 636 | 212 | 150 | 247 | 0.4049 | 0.6667 | 0.5038 | **0.6821** |

القاعدة لم تُعد معايرتها في confirmation. لذلك تمثل confirmation إعادة تشغيل زمنية لاحقة للصيغة نفسها، لا اختياراً جديداً.

## baselines

في كل split، بقيت القاعدة فوق always-negative وalways-positive من حيث Balanced Accuracy؛ كلاهما BA=`0.5`. هذا لا يكفي وحده، لأن high-growth هو تعريف trigger وقد يتأثر بمعدل حدوث outcome. القيمة المهمة هي أن confirmation بقيت BA=`0.6821` رغم انخفاض F1 عن validation، ما يعني أن الإشارة لم تختفِ بالكامل عند الانتقال إلى سنوات لاحقة.

## Null Controls

شُغلت 2,000 label permutation داخل كل CountryID لكل من validation وconfirmation. حافظ كل تكرار على بنية الكيان وعدد الحالات داخل الكيان، ثم قورنت النتيجة المرصودة بتوزيع الأداء العشوائي.

| Split | Observed BA | Null BA mean | Null BA 97.5% | Observed F1 | Null F1 mean | Null F1 97.5% | p BA | p F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Validation | 0.7325 | 0.6076 | 0.6311 | 0.6185 | 0.4820 | 0.5077 | 0.0005 | 0.0005 |
| Confirmation | 0.6821 | 0.6014 | 0.6298 | 0.5038 | 0.4106 | 0.4433 | 0.0005 | 0.0005 |

هذه المقارنة تثبت أن قاعدة high-growth على AMA ليست متوافقة مع label permutation العشوائية في الجزأين المختبرين. لكنها لا تجعل القاعدة سببية، ولا تلغي احتمال وجود تغيرات منهجية أو prevalence أو اعتماد على تعريف material deterioration.

## ماذا تكرر وماذا لم يتكرر؟

الذي تكرر هو اتجاه عام: النمو الحالي الأعلى من 4% ارتبط لاحقاً باحتمال أعلى لتدهور لا يقل عن نقطتين مئويتين خلال ثلاث سنوات، حتى بعد نقل الصيغة إلى مصدر AMA مستقل.

الذي لم يثبت هو أن لدينا مساراً مركباً أو آلية سببية. replication الحالية لا تقول إن population أو energy/GDP عقدتان ضروريتان. كما لا تقول إن القاعدة تتنبأ بانكماش حاد؛ اختبارات CHAOS السابقة أظهرت أن contraction وonset contraction كانا أضعف من material deterioration.

## القيود

أولاً، AMA مصدر مستقل، لكنه ليس بالضرورة مستقلاً منهجياً عن كل مصادر الحسابات القومية العالمية؛ الصفحة الرسمية نفسها تذكر استخدام تقديرات عند نقص البيانات الرسمية. ثانياً، التغطية المتاحة ليست متساوية لكل CountryID وكل سنة، ولذلك استُخدم complete-case eligibility بدلاً من ملء الفجوات. ثالثاً، النتيجة ما زالت مشتقة من مصدر اقتصادي واحد، وليست اختباراً على الأحداث السياسية أو الكوارث أو الطاقة. رابعاً، عدم استخدام 2020–2024 يقلل خطر إعادة استخدام test السابق، لكنه يجعل confirmation ممتدة حتى 2019 فقط.

## القرار

أصنف النتيجة كالتالي:

```text
independent-source descriptive replication: supported
outcome-specific high-growth association: supported provisionally
bounded population/energy proxy contribution: not supported as necessary
causal pattern: not established
operational promotion: rejected
```

الخطوة التالية المناسبة ليست تعديل العتبة أو إعادة اختيار outcome داخل AMA. إذا استمر العمل، ينبغي تجميد هذه الصيغة كما هي، ثم إضافة مصدر مستقل ثانٍ أو outcome مستقل غير اقتصادي، مع الحفاظ على الفروق المنهجية وعدم الدمج القسري. لا ينبغي تحويل النتيجة إلى خوارزمية تشغيلية قبل تكرارها في مصدر مستقل آخر أو domain مستقل.

## الملفات المحفوظة

تم حفظ الخام خارج التحليل المشتق، وملف staging، وmetadata، والعقد، ومقاييس كل split، وNull Controls، وسجل التنفيذ داخل CHAOS. لم يُفتح locked test السابق، ولم تُعدل البيانات الخام، ولم تُستخدم imputation أو normalization.

### References

[1]: https://unstats.un.org/unsd/snaama/downloads "UN Statistics Division — National Accounts AMA Downloads"
[2]: https://unstats.un.org/unsd/snaama/ "UN Statistics Division — National Accounts Main Aggregates"
[3]: https://www.rug.nl/ggdc/productivity/pwt/?lang=en "Penn World Table 11.0 — official page screened as an alternative independent source"
