# تقرير Domain State وPath Composition

## الخلاصة

اكتملت طبقة أولية تفصل بين **الحالة الحالية** و**دليل الانتقال** و**التركيب الاحتمالي للمسارات**. بُنيت الحالات من مصدرين حقيقيين: UN AMA الاقتصادي وUCDP Country-Year للصراع. ثم أُعيد تقييم الروابط التي ظهرت في المراحل السابقة، وجُرب وسيط طاقي، وبُني Path Composer احتمالي بأوزان مقدرة من fit فقط.

النتيجة المهنية الصريحة هي أن البنية البرمجية تعمل، لكن تركيب الوسيط الطاقي لم يضف قيمة خارج fit. لذلك بقي المسار الاقتصادي الأساسي وحده هو المرشح المدعوم، بينما ظلت حافة UCDP مغلقة وغير مفعلة.

## 1. DomainState

يحتوي `DOMAIN_STATES_V1` على 25,192 سجلاً سنوياً:

| المجال | السجلات | التواتر | المصدر |
|---|---:|---|---|
| Economic | 10,928 | Annual | UN AMA January 2026 |
| Conflict | 14,264 | Annual | UCDP Organized Violence Country-Year 26.1 |
| الإجمالي | 25,192 | Annual | مصدران منفصلان |

الحالة الاقتصادية الحالية هي `high_growth_gt_4pp` أو `non_high_growth`. الحالة الصراعية الحالية هي `state_based_conflict_present` أو `no_state_based_conflict`، مع حالة مستقلة لـ`state_based_high_fatality_25_plus`.

الحالات الاحتمالية هنا هي **rule scores**: القيمة 1 تعني أن الشرط الوصفي تحقق، والقيمة 0 تعني عدم تحققه. لا تمثل احتمالاً سببياً أو ثقة سببية.

## 2. TransitionEvidence

تم تسجيل ثمانية edges:

| الحالة | العدد |
|---|---:|
| supported_predictive | 2 |
| rejected | 5 |
| unresolved | 1 |
| causal claims | 0 |

الرابط الوحيد المدعوم حالياً هو:

```text
AMA high-growth >4%
→ AMA material GDP deterioration within 3 years
```

الرابط الاقتصادي-الصراعي:

```text
AMA high-growth >4%
→ UCDP state-based conflict after 3 years
```

بقي مرفوضاً بعد Null Controls. أما high-fatality فبقي غير محسوم وضعيفاً، ولم يُفعل في Path Composer.

## 3. اختبار الوسيط الطاقي

اختُبرت أربعة مسارات محددة مسبقاً: high-growth مع انخفاض أو ارتفاع energy/GDP بعد سنة أو سنتين، ثم material deterioration بعد ثلاث سنوات.

| Split | أفضل مسار وسيط | BA الوسيط | BA high-growth baseline |
|---|---|---:|---:|
| Validation | energy/GDP down at t+2 | 0.6254 | 0.7382 |
| Confirmation | energy/GDP down at t+2 | 0.6347 | 0.6536 |

رغم أن أفضل وسيط داخل شبكة المسارات تجاوز null الخاص بالمسارات الأربعة، فإنه لم يتفوق على high-growth baseline. لذلك سجلته:

```text
candidate_mediator_without_additive_gain
```

لا توجد حالياً أدلة تبرر جعل energy/GDP عقدة ضرورية بين high-growth والتدهور.

## 4. Path Composer

بُني `PATH_COMPOSER_V1_1` كتركيب احتمالي لا كجمع اعتباطي للأوزان. قُدرت الاحتمالات من fit 2006–2009 فقط:

```text
p_base = 0.3853
p_high_growth = 0.6000
p_high_growth_energy_down_t2 = 0.6740
```

الصيغة:

```text
p = p_base                          إذا لم يكن high-growth
p = p_high_growth                   إذا كان high-growth دون mediator
p = p_high_growth_energy_down_t2    إذا تحقق mediator
```

| Split | Composer BA | Baseline BA | Composer Brier | Baseline Brier | Composer Log-loss | Baseline Log-loss |
|---|---:|---:|---:|---:|---:|---:|
| Fit | 0.7361 | 0.7361 | 0.2109 | 0.2127 | 0.6135 | 0.6175 |
| Inner | 0.7336 | 0.7336 | 0.2197 | 0.2149 | 0.6324 | 0.6219 |
| Validation | 0.6818 | 0.6818 | 0.2284 | 0.2184 | 0.6505 | 0.6289 |
| Confirmation | 0.5787 | 0.5787 | 0.2458 | 0.2400 | 0.6856 | 0.6730 |

التركيب تحسن داخل fit فقط، ثم أصبح أسوأ في inner وvalidation وconfirmation. هذا overfitting محدود لكنه واضح بما يكفي لرفض mediator في النسخة الحالية. التشابه في BA سببه أن threshold الثنائي لم يغير معظم قرارات high-growth؛ لذلك Brier وlog-loss أكثر إفادة هنا.

## 5. الشكل الذي يجب أن يبقى

```text
DomainState adapters
    ↓
TransitionEvidence
    ↓
Path candidates
    ↓
Null / OOS / stability
    ↓
Pattern registry
    ↓
Compatibility adapter لاحقاً
```

يجب أن يبقى UCDP edge غير مفعل، ويجب أن يبقى energy mediator مرشحاً مرفوضاً من حيث الإضافة الحالية، لا أن يُحذف من السجل.

## القرار

أوصي باعتماد المعمارية البرمجية، وعدم اعتماد Path Composer v1.1 كخوارزمية. المسار الاقتصادي الأساسي يحتفظ بحالة `supported_predictive` وصفية فقط. قبل أي runtime promotion، يلزم مصدر اقتصادي مستقل آخر أو outcome مستقل يدعم الانتقال نفسه، ثم Composer يعاير احتمالاته على أكثر من فترة دون تحسن fit فقط.

لم تُستخدم imputation أو normalization أو source averaging، ولم تُدمج التواترات المختلفة. locked test السابق لم يُفتح، وGED اليومي لم يُحوّل إلى سنوي.
