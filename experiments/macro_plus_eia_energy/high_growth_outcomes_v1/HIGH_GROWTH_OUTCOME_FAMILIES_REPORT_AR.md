# تقرير High-Growth عبر عائلات النتائج والـLead Horizons

## القرار المختصر

بعد أن أظهر locked test أن population وenergy-per-GDP لم يضيفا قيمة فوق high current growth وحده، فُصلت فرضية النمو المرتفع واختُبرت مباشرة عبر سبع عائلات نتائج وثلاثة horizons، على discovery وvalidation قبل test السابق فقط. جرى اختبار 21 تعريفاً ثابتاً بقاعدة واحدة:

```text
target[t] > 4.0
```

لم يُفتح locked test السابق ولم تُستخدم سنوات 2020–2024 في هذه المقارنة.

النتيجة: الإشارة لا تظهر بالطريقة نفسها في كل Outcome Family. أقوى العائلات كانت `deterioration` و`material_drop_2pp`، خصوصاً عند horizon ثلاث سنوات. أما `contraction` و`onset_contraction` و`adverse_tail` و`persistent_contraction` فكانت ضعيفة أو قريبة من الصدفة. لذلك لا توجد حالياً «نتيجة واحدة عامة»؛ توجد إشارة outcome-specific مرتبطة بتدهور أو انخفاض مادي، لا بإطلاق contraction حاد بالضرورة.

## نطاق البحث

| البعد | القيم |
|---|---|
| Rule | `target[t] > 4.0` |
| Outcome Families | contraction، onset contraction، material drop 2pp، deterioration، adverse tail q10، any contraction، persistent contraction |
| Horizons | 1، 2، 3 سنوات |
| عدد المواصفات | 21 |
| Validation windows | 2014–2016، 2016–2019، 2015–2018 حسب fold |
| locked test السابق | مغلق ولم يُعاد فتحه |
| Null | 2,000 entity-label permutation مع max-stat عبر كامل 21 مواصفة |

## نتائج validation المجمعة

| Family | h=1 BA | h=2 BA | h=3 BA | h=3 F1 | التفسير الأولي |
|---|---:|---:|---:|---:|---|
| deterioration | 0.6547 | 0.6920 | **0.7194** | **0.6868** | أقوى إشارة، لكنها outcome واسعة |
| material_drop_2pp | 0.6531 | 0.7086 | **0.7194** | 0.4914 | إشارة مادية متكررة عند h=3 |
| onset_contraction | 0.4150 تقريباً | 0.4975 | 0.5257 | 0.1048 | ضعيفة وقريبة من BA العشوائي |
| contraction | 0.3489 تقريباً | 0.4473 | 0.4531 | 0.1001 | لم تتكرر كإشارة قوية |
| adverse_tail_q10 | 0.3382 | 0.4263 | 0.4146 | 0.0543 | rare tail ضعيف الدعم |
| any_contraction | 0.3417 | 0.4233 | 0.4232 | 0.1728 | لا يدعم إنذار contraction داخل نافذة |
| persistent_contraction | 0.3417 | 0.3159 | 0.3426 | 0.0064 | نادر جداً وغير عملي في هذه اللوحة |

القيم المجمعة هي متوسط folds الثلاثة، ولا تعني أن كل fold متساوٍ في prevalence أو عدد الحالات. لذلك تحفظ الجداول التفصيلية لكل fold ولا يُستبدل بها المتوسط وحده.

## القراءة المهمة للـOutcome Families

القاعدة `target[t] > 4.0` لا تتنبأ جيداً ببدء contraction حاد في السنة التالية؛ أداؤها عند `onset_contraction` في validation بقي قريباً من BA=`0.5` أو أدنى في بعض folds. لكنها ارتبطت أكثر بتعريفات التدهور الأوسع، خصوصاً انخفاض الهدف عن origin أو انخفاضه بمقدار نقطتين مئويتين بعد ثلاث سنوات.

هذا يغير صياغة الفكرة. لا ينبغي أن نقول إن high growth «ينذر بانكماش» بالمعنى الحاد. الصياغة الأقرب إلى البيانات هي:

> high current growth قد يكون علامة على احتمال تدهور أو material drop لاحق، بينما لا تكفي هذه القاعدة وحدها لتوقع onset contraction حاد.

هذه ليست سببية، وقد تكون mean reversion أو أثراً لتعريف النتيجة نفسه.

## أفضل نتيجة ومسألة prevalence

أفضل مواصفة حسب BA وF1 كانت:

```text
family = deterioration
horizon = 3
rule = target[t] > 4.0
```

بمتوسط BA=`0.7194` وF1=`0.6868`. لكن `deterioration` تعريف واسع، ولذلك يملك prevalence أعلى من contraction. لا يجوز مقارنة F1 بين العائلات وكأنها أهداف متساوية الصعوبة. لهذا السبب بقي `material_drop_2pp` هو العائلة الأهم للتفسير التشغيلي المحتمل، واعتبرت deterioration نتيجة داعمة لا بديلاً عنها.

لـ`material_drop_2pp`، كان المتوسط عند h=3 هو BA=`0.7194` وF1=`0.4914`، مع دعم مناسب مقارنة بعائلات tail أو persistent contraction. هذا يكرر الاتجاه الذي ظهر في شبكة threshold السابقة، لكن من دون إضافة bounded population أو energy/GDP.

## Null Controls مع تصحيح البحث المتعدد

تم تطبيق label permutation داخل الكيان على كل من الثلاثة folds، ثم حساب أفضل متوسط BA وأفضل متوسط F1 عبر كامل شبكة الـ21 مواصفة في كل replicate.

| الإحصاء | المرصود الأفضل | متوسط max-null | 97.5% max-null | p التجريبية العليا |
|---|---:|---:|---:|---:|
| Balanced Accuracy | 0.7194 | 0.6119 | 0.6271 | 0.0005 |
| F1 | 0.6868 | 0.5651 | 0.5822 | 0.0005 |

هذا يعني أن أفضل نتيجة في الشبكة أبعد من أفضل نتيجة عشوائية في نفس الشبكة. لكنه لا يثبت أن outcome family الأفضل هو «الحقيقة»؛ اختيار deterioration بعد البحث لا يحولها إلى outcome محايد. النتيجة الصحيحة هي أن high-growth يحمل إشارة أقوى مع deterioration/material drop، وأضعف مع contraction/onset/tail.

## ما الذي نحتفظ به كمرشح؟

أحتفظ بالصيغة التالية كـcandidate family-specific:

```text
high current growth (target[t] > 4.0)
→ material deterioration over a 3-year horizon
```

وأرفض مؤقتاً الصيغ التالية كمرشحين مثبتين:

```text
high growth → immediate contraction
high growth → onset contraction
high growth → persistent contraction
high growth → rare adverse-tail event
```

هذا الرفض لا يعني أن هذه النتائج مستحيلة؛ بل إن هذه اللوحة وهذا التعريف وهذا lead لم يعطوا دعماً كافياً.

## ما لم يُنفذ

لم يُستخدم locked test السابق، ولم تُعاد معايرة threshold بعد رؤية النتائج، ولم تُجمع بيانات جديدة، ولم تُعدل raw، ولم تُستخدم imputation أو normalization. كما لم تُحوّل هذه النتيجة إلى خوارزمية تشغيلية أو ادعاء سببي.

## القرار التالي

الخطوة المناسبة ليست فتح test مرة أخرى. المسار الأفضل هو تثبيت `material_drop_2pp @ h=3` كعائلة أساسية، ثم اختبار صيغة high-growth وحدها على outcome definitions مستقلة في مصدر أو لوحة أخرى، أو إضافة متغيرات أحداث ذات native frequency منفصلة. إذا تكررت الإشارة خارج هذه اللوحة، يصبح لدينا دليل تعميم أفضل. وإذا لم تتكرر، تسجل كـmacro_plus_eia panel association.

**الحالة الحالية:** discovery/validation اكتمل، null max-stat اكتمل، locked test السابق بقي مغلقاً، والترقية التشغيلية مرفوضة حتى يظهر تكرار مستقل.
