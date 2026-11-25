# CHAOS — Terminology and Relationships

## 1. وظيفة هذا الملف

هذا الملف هو المرجع المشترك لمصطلحات مشروع **CHAOS**. يهدف إلى حفظ الترابط الأساسي بين طبقات البحث، ومنع استخدام الكلمة نفسها بمعانٍ مختلفة بين الوكلاء والـadapters والـEvidence Graph والـPattern Compiler والـResearch Runtime.

لا يفرض هذا الملف نموذجاً رياضياً نهائياً، ولا يحوّل المصطلحات إلى ادعاءات سببية. إنما يحدد **ما الذي يعنيه كل مصطلح داخل المختبر، وما الذي لا يعنيه**، وأين يقع في خط العمل:

```text
Source Asset
  → ObservedRecord
  → DomainState
  → TransitionEvidence / Edge
  → Path
  → Pattern
  → Research Runtime Artifact
```

> القاعدة المركزية: **وجود مصطلح أو حالة أو حافة في CHAOS لا يعني أنها مثبتة أو سببية أو صالحة للتشغيل.** حالة الدليل منفصلة دائماً عن اسم الكيان أو العقدة.

## 2. النموذج الهرمي الأساسي

| المستوى | المصطلح | الوظيفة | يخرج منه |
|---|---|---|---|
| 0 | `Source Asset` | ملف أو API أو أرشيف أو سجل خارجي كما وصل من المصدر | خام محفوظ وـprovenance |
| 1 | `ObservedRecord` | تمثيل مشاهدة مصدرية واحدة دون تفسير زائد | ملاحظة قابلة للفهرسة |
| 2 | `DomainState` | توصيف حالة مجال عند زمن محدد وفق قاعدة معلنة | عقدة حالة |
| 3 | `TransitionEvidence` / `Edge` | اختبار انتقال مؤرخ من حالة إلى أخرى | دليل انتقال وحالته المنهجية |
| 4 | `Path` | تسلسل حواف وحالات قد يفسر مساراً تاريخياً | مسار مركب أو متنافس |
| 5 | `Pattern` | قاعدة أو بنية تكررت أو بقيت مرشحة بعد الاختبار | Pattern Artifact بحثي |
| 6 | `Research Runtime Artifact` | نسخة قابلة لإعادة التشغيل داخل المسار المعزول | alert بحثي مع evidence وuncertainty |
| 7 | `Runtime Compatibility` | قرار منفصل لاحق حول قابلية استهلاك artifact خارج المختبر | ليس مفعلاً تلقائياً |

العلاقة المختصرة هي:

```text
Domain CONTAINS State
State IS_DEFINED_BY Observations
State PARTICIPATES_IN Edge
Edge COMPOSES Path
Path MAY_FORM Pattern
Pattern IS_SUPPORTED_BY Evidence
Pattern MAY_BE_COMPILED_INTO Research Runtime Artifact
Research Runtime Artifact MAY_BE_REVIEWED_FOR Runtime Compatibility
```

كل علاقة من هذه العلاقات قابلة للفشل أو التأجيل. كلمة `MAY` مقصودة؛ فهي تمنع افتراض أن كل حالة ستصبح حافة، أو أن كل حافة ستصبح مساراً، أو أن كل مسار سيصبح Pattern.

## 3. المصطلحات الأساسية

### 3.1 `Source Asset`

هو الأصل الخارجي الذي تم تنزيله أو الوصول إليه أو فهرسته: CSV، JSON، XLSX، ZIP، API response، سجل حدثي، أو ملف metadata. يبقى خاماً وغير معدل، وتُحفظ نسخته وهاشه ورابطه وإصدار المصدر وشروط استخدامه.

لا يعني `Source Asset` أنه كامل أو صحيح مطلقاً أو قابل للمقارنة مع مصدر آخر. قد يكون asset حقيقياً لكنه محدود التغطية أو متغير التعريف أو غير قابل للاستخدام في تجربة معينة.

### 3.2 `Source Manifest`

هو سجل يصف الـSource Asset: المصدر، الإصدار أو vintage، رابط الوصول، وقت الجمع، الحجم، الهاش، التواتر، نطاق السنوات، الوحدة، شروط الاستخدام، وحالة التنزيل.

الـmanifest لا يستبدل البيانات ولا يثبت جودة القياس؛ إنه يثبت **ما الذي وصل إلينا وكيف وصل**.

### 3.3 `ObservedRecord`

هو مشاهدة واحدة محفوظة مع سياقها، وتشمل عادة:

```text
source_id
source_version
entity_id
observation_time
publication_or_update_time إن توفر
variable_id أو event_id
raw_value أو raw_payload
unit
native_frequency
definition
provenance_ref
quality_or_coverage_flags
```

لا يجوز أن يحتوي `ObservedRecord` على label مستقبلي أو تفسير سببي أُضيف بعد وقوع النتيجة. يمكن حفظ قيم مشتقة في طبقة منفصلة، لكن لا تحل محل الأصل الخام.

### 3.4 `Provenance`

هو سلسلة أصل الدليل: المصدر، الملف أو endpoint، الإصدار، الرابط، وقت الجمع، الهاش، التحويل المشتق إن وجد، ومرجع السجل. provenance يجيب عن سؤال: **من أين جاءت هذه القيمة وما الذي حدث لها؟**

`provenance` ليس مرادفاً لـ`quality`. قد يكون مصدر موثقاً لكنه غير مكتمل أو مختلف التعريف.

### 3.5 `Entity`

هو وحدة المطابقة التي تُسند إليها مشاهدة أو حالة: دولة، إقليم، محطة، موقع، شركة، ميناء، حدث ذي إحداثيات، أو كيان آخر يحدده المصدر.

في CHAOS لا تعني مطابقة الاسم أن الكيانات متطابقة مفاهيمياً. لا يجوز دمج دولة مع aggregate أو محطة مع متوسط وطني أو حدث زلزالي مع دولة لمجرد تشابه الاسم. المطابقة نفسها لها `crosswalk` وprovenance وحالة نجاح أو فشل.

### 3.6 `Domain`

هو مجال من مجالات الواقع له تعريفات ومصادر وتواتر وقيود خاصة، مثل:

```text
economic
energy
trade
conflict
health_pandemic
disaster_seismic
environment_climate
institutions_policy
transport_infrastructure
social_demography
```

`Domain` ليس متغيراً واحداً ولا تفسيراً سببياً. هو حاوية تنظيمية تفصل قواعد القياس قبل الربط بين المجالات.

### 3.7 `Native Frequency`

هو التواتر الذي جاء به المصدر أو الذي يعرّفه المصدر: `event`، `daily`، `weekly`، `monthly`، `quarterly`، `annual`، أو غيرها.

الحفاظ على التواتر الأصلي شرط علمي ومعماري. لا يجوز تحويل daily أو event إلى annual لمجرد إدخاله في لوحة اقتصادية. أي محاذاة بين تواترين تحتاج `Temporal Alignment Contract` مستقلاً.

### 3.8 `Coverage`

هي التغطية الفعلية للكيانات والزمن والحقول، لا التغطية النظرية التي يعلنها الكتالوج. تشمل بداية ونهاية المشاهدة، عدد الكيانات، الفجوات، الخانات الفارغة، الانقطاعات، والتحولات المنهجية.

التقاطع الاسمي بين مصدرين لا يساوي تقاطعاً كاملاً صالحاً للاختبار.

### 3.9 `Event`

واقعة مؤرخة يصفها المصدر، مثل زلزال أو تفشٍ صحي أو قرار أو إضراب أو تغيير مؤسسي. يحتفظ الحدث بوقت المصدر ونطاقه وخصائصه ومصدره.

`Event` لا يعني تلقائياً `Shock`، ولا يعني أنه سبب نتيجة. يحتاج الانتقال من الحدث إلى الأثر إلى قياس أو عقد منفصل.

### 3.10 `Exposure`

مقدار أو نطاق تعرض كيان لحدث أو ضغط: موقع جغرافي، سكان متأثرون، قطاع، بنية تحتية، أو نطاق زمني. قد يكون التعرض مفقوداً حتى لو كان الحدث موثقاً.

### 3.11 `Shock`

أثر أو اضطراب مشتق من ملاحظة أو حدث وفق تعريف معلن. في مسار الكوارث والجوائح يجب الفصل بين:

```text
Event → Exposure → Production / Supply / Mobility Shock → Recovery
```

لا يجوز تسمية كل حدث `shock` بلا قياس للأثر. و`shock` ليس مرادفاً للنتيجة النهائية.

### 3.12 `Production Shock`

تغير أو اضطراب في الإنتاج أو القدرة التشغيلية أو العرض بعد حدث أو قرار، وفق مقياس مصدره أو عقد قياس واضح. وجود حدث طبيعي وحده لا يثبت production shock.

### 3.13 `Recovery`

حالة أو انتقال يصف استعادة مؤشّر أو قدرة أو تدفق وفق baseline وتعريف معلنين. يجب تحديد ما إذا كان التعافي عودة إلى المستوى السابق، أو تجاوزاً له، أو مجرد توقف في التدهور.

`Recovery` ليست بالضرورة نهاية الخطر؛ قد يحدث تعافٍ جزئي مع استمرار ضرر أو انتقال إلى مسار جديد.

## 4. طبقة الحالات والانتقالات

### 4.1 `State`

وصف لحالة النظام أو المجال في زمن محدد. الحالة ليست event، وليست outcome مستقبلياً، وليست احتمالاً سببياً.

لكل State يجب تحديد:

```text
state_id
domain
entity
timestamp
native_frequency
entry_rule
exit_rule
duration_or_expiry
source_observations
uncertainty
failure_cases
```

### 4.2 `DomainState`

الواجهة الموحدة للحالة داخل مجال محدد. الشكل المفاهيمي هو:

```text
DomainState {
  domain,
  entity,
  timestamp,
  native_frequency,
  regime_label,
  regime_probability,
  source_observations,
  lead_profile,
  uncertainty,
  failure_cases,
  evidence_refs
}
```

`DomainState` يوحد البنية البرمجية، ولا يوحد تعريف المصدر أو وحدته أو تواتره قسراً.

### 4.3 `Regime`

منطقة أو وضع مستمر نسبياً في القياسات أو القيود، مثل `high_growth` أو `energy_stress`. يجب أن يكون له rule أو model معلن.

`Regime` ليس مرادفاً للنظام السياسي، ولا يعني سببية. قد يكون regime اقتصادي أو مؤسسي أو مناخي، ويجب ألا تختلط هذه المعاني.

### 4.4 `Outcome`

النتيجة التي تُقاس بعد نقطة الأصل أو بعد أفق زمني. مثال: `material_deterioration` عند `t+3` أو `future_state_conflict`.

لا يجوز استخدام outcome المستقبلي لتعريف الحالة الحالية أو اختيار threshold أو grouping أو configuration.

### 4.5 `Transition`

انتقال زمني من حالة إلى أخرى. كلمة transition تصف ترتيباً زمنياً، ولا تثبت السببية وحدها.

### 4.6 `Edge`

تمثيل مختصر لحافة انتقال بين حالتين أو عقدتين. قد تكون داخل المجال أو عابرة للمجالات. لا تصبح edge مدعومة إلا بعد عقد وتجربة واختبارات null وOOS وثبات مناسبة.

### 4.7 `TransitionEvidence`

سجل الدليل المنفصل للحافة، ويشمل:

```text
source_state
target_state
lag / window
native frequencies
chronological split
metric
baseline
null_method
p_value أو null summary
entity_holdout
source_refs
failure_cases
edge_status
causal_claim
```

هو سجل اختبار، وليس مجرد رسم سهم. يمكن أن تكون الحافة نفسها مدعومة في validation وفاشلة في confirmation؛ يجب حفظ كل split بدلاً من إخفائه.

### 4.8 `Lag`, `Lead`, `Horizon`, `Window`

| المصطلح | المعنى في CHAOS |
|---|---|
| `Lead` | أن ملاحظة أو حالة تأتي زمنياً قبل أخرى |
| `Lag` | الفاصل الزمني بين المصدر والهدف، مع وحدة واتجاه |
| `Horizon` | الأفق الذي تُقاس عنده النتيجة، مثل `t+3 years` |
| `Window` | فترة بداية/نهاية تستخدم لتعريف حدث أو أثر أو تعافٍ |

لا يجوز استعمال `lag=3` من دون تحديد أن الوحدة سنوات أو أيام أو شهور، ولا استعمال midpoint بدلاً من وقت الحدث دون عقد.

### 4.9 `Mediator`

حالة أو متغير يقع بين source state وtarget state ضمن مسار زمني معلن. mediator في CHAOS مرشح لمسار، وليس برهاناً على آلية سببية.

### 4.10 `Confounder` و`Common Shock`

`Confounder` عامل قد يرتبط بالمصدر والهدف ويخلق أو يغير العلاقة المرصودة. `Common Shock` اضطراب مشترك يؤثر في أكثر من مجال.

إذا لم يُقَس العامل أو لا يمكن اختباره، يحفظ كـ`uncertainty_ref` أو تفسير منافس، ولا يُخترع له عمود بيانات.

### 4.11 `Hidden / Unmeasured Factor`

عامل غير مرصود أو غير متاح قد يفسر جزءاً من النتيجة. وجوده لا يبرر نظرية غير موثقة، لكنه يمنع الادعاء بأن الرسم المرصود هو تفسير كامل.

## 5. طبقة المسارات والأنماط

### 5.1 `Path`

تسلسل من حالات وحواف مرتبة زمنياً، مثل:

```text
high_growth
  → material_deterioration
  → energy_stress
```

لا يكفي أن تكون كل عقدة معقولة؛ يجب اختبار كل edge، ثم اختبار المسار ككل مقابل baselines وnull وOOS.

### 5.2 `Competing Path`

مسار بديل يفسر الوقائع نفسها أو جزءاً منها. يجب أن يحتفظ CHAOS بالمسارات المتنافسة، بما في ذلك:

```text
economic deterioration → conflict
policy shock → trade disruption → deterioration
common external shock → apparent co-movement
unmeasured factor → unresolved
```

عدم القدرة على التمييز بين المسارات نتيجة بحثية `unresolved` وليست سبباً لاختيار المسار الأكثر جاذبية سردياً.

### 5.3 `Pattern`

قاعدة أو بنية أو تسلسل بقي مرشحاً بعد اختبارات محددة، مثل:

```text
high current GDP growth (>4%)
  → material GDP deterioration within 3 years
```

`Pattern` لا يعني تلقائياً أنه ناجح أو سببي أو صالح للتشغيل. لذلك يجب أن يحمل status وevidence وfailure cases.

### 5.4 `Pattern Artifact`

ملف قابل للحفظ وإعادة القراءة يصف pattern، وقاعدة الكشف عنه، ومصادره، وحدوده، ونسخته، وحالته. لا يجوز أن يخفي فشل المسار أو uncertainty.

### 5.5 `Pattern Compiler`

طبقة تحول pattern مقبولاً بحثياً إلى مواصفة كشف قابلة لإعادة التشغيل. لا تعني أن pattern أصبح production rule. يجب أن يخرج compiler على الأقل:

```text
pattern_id
rule
required_states
required_evidence_refs
status
runtime_eligible
failure_cases
uncertainty
```

## 6. التقييم والإثبات

### 6.1 `Descriptive`

وصف لما حدث في البيانات أو ما يتكرر فيها. لا يثبت أن أحد المتغيرات سبب الآخر.

### 6.2 `Predictive`

قدرة قاعدة أو نموذج على التمييز أو التنبؤ بنتيجة مستقبلية تحت عقد وتقسيم محددين. الأداء التنبؤي لا يساوي السببية.

### 6.3 `Causal`

ادعاء بأن تغيراً في عامل يؤدي إلى تغير في نتيجة عبر تصميم سببي مبرر، مع افتراضات واختبارات مناسبة. لا تُستخدم كلمات `cause`, `driver`, `mechanism`, أو `causal` في CHAOS لمجرد أن edge زمنية أو أن metric تحسن.

### 6.4 `Baseline`

مرجع بسيط تقارن به الحافة أو المسار، مثل prevalence classifier أو target-history أو high-growth-only baseline. عدم التفوق على baseline يعني أن التعقيد الإضافي لم يثبت قيمته.

### 6.5 `Null Control`

اختبار يبني توزيعاً مرجعياً تحت غياب العلاقة المراد اختبارها، مثل within-entity label permutation أو time/block shift. null ليس إثباتاً لعدم وجود علاقة في الكون كله؛ إنه اختبار محدد تحت تصميم محدد.

### 6.6 `Max-Statistic Correction`

تصحيح يحاسب عن البحث عبر thresholds أو horizons أو outcome families أو paths. تقارن أفضل نتيجة مرصودة بأفضل نتائج null عبر نفس فضاء البحث، لا بnull لخلية واحدة فقط.

### 6.7 `OOS — Out of Sample`

اختبار على بيانات لم تدخل اختيار القاعدة أو threshold أو configuration. يشمل validation أو confirmation حسب العقد. استخدام test لاختيار configuration يلغي معنى OOS.

### 6.8 `Chronological Split`

تقسيم زمني يحترم اتجاه الزمن، مثل:

```text
fit → validation → confirmation / test
```

لا يسمح بتسريب المستقبل إلى تعريف الحالة أو اختيار النمط.

### 6.9 `Entity Holdout`

اختبار على كيانات لم تدخل fit أو اختيار القاعدة، ويقيس ما إذا كان النمط خاصاً بمجموعة كيانات محددة.

### 6.10 `Stability`

مدى بقاء النتيجة عبر seeds أو periods أو entities أو definitions أو splits المسموح بها. الاستقرار لا يثبت السببية، لكنه يقلل احتمال أن تكون النتيجة artifact محلياً.

### 6.11 `Calibration`, `Brier`, `Log-loss`, `Balanced Accuracy`, `F1`

هذه مقاييس أداء مختلفة، ولا يجوز اختزالها في رقم واحد دون عقد. `Brier` و`log-loss` يفيدان في تقييم الاحتمالات، و`balanced accuracy` تعالج اختلال الفئات جزئياً، و`F1` يوازن precision وrecall وفق التعريف المستخدم.

### 6.12 `Prevalence`

نسبة الحالات الموجبة في العينة أو split. قد تتغير بين الفترات والكيانات، ولذلك لا يكفي أن يكون BA فوق 0.5 دون معرفة prevalence والbaseline.

### 6.13 `Attention`, `Feature Importance`, `Transition Score`

مخرجات تفسيرية أو ترتيبية من نموذج أو graph. لا تعتبر دليلاً سببياً. يمكن حفظها كـcandidate temporal/structural patterns فقط، مع عدم ترقيتها إلى mechanism أو weight تشغيلي.

## 7. البيانات الناقصة والتحويلات

### 7.1 `Missingness` و`Gap`

`Missingness` غياب قيمة أو سجل، و`Gap` فجوة زمنية أو جغرافية في التغطية. الخانة الفارغة ليست صفراً إلا إذا قال المصدر ذلك صراحة.

### 7.2 `Complete-case`

استخدام السجلات المكتملة للحافة أو التجربة المحددة، مع حفظ السجلات المستبعدة وسبب الاستبعاد. complete-case ليس imputation ولا يبرر إعلان أن المصدر كاملاً.

### 7.3 `Imputation`

تقدير قيمة غير مرصودة من قيم أخرى. ممنوع في الطبقات الحالية ما لم يُنشأ عقد مستقل يحدد طريقته وموضعه وتأثيره، ولا يجوز الكتابة فوق الخام.

### 7.4 `Transformation`

أي log، difference، return، normalization، z-score، smoothing، resampling أو اشتقاق آخر. التحويل ليس تنظيفاً محايداً تلقائياً؛ يجب أن يعلن في عقد منفصل.

### 7.5 `Source Reconciliation`

دمج أو متوسط أو اختيار قسري بين مصادر مختلفة لتعريف واحد. لا يُسمح به تلقائياً؛ تحفظ مصادر القياس وتعارضاتها أولاً.

## 8. البنية الدنيا وأدوارها

### 8.1 `Source Adapter`

مترجم حدودي خاص بمصدر واحد. يقرأ المصدر المصرح به، ويحفظ تعريفه ووحدته وتواتره، وينتج `ObservedRecord` أو `DomainState` مع provenance. لا يقرر أن المصدر سبب، ولا يدمج مصادر متعارضة قسراً.

### 8.2 `Domain Adapter`

واجهة تنقل observations إلى حالات مجال موحدة البنية. يمكن أن يكون لها أكثر من source adapter، لكن لا يجوز أن تخفي اختلافات القياس.

### 8.3 `Temporal Alignment Engine`

أداة محكومة تنفذ محاذاة معلنة بين تواترين أو نافذتين. لا تغير الخام، وتنتج derived alignment artifact مع counts وdropped records وhashes وسبب كل استبعاد.

### 8.4 `Research Ledger`

سجل append-only للعقود والتجارب والحالات والحواف والقرارات والمخرجات. يربط كل record بالمدخلات والمخرجات والهاش والوقت والحالة.

### 8.5 `Evidence Graph Builder`

أداة تبني graph من DomainStates وTransitionEvidence والسجل المتحكم. تحتفظ بالمرفوض وغير المحسوم وnot_testable داخل الرسم، لكنها تمنعها من الدخول بوزن موجب في المسار المركب.

### 8.6 `Path Composer`

طبقة تقارن مسارات مدعومة، لا آلة لجمع scores عشوائياً. يجب أن تقارن كل path بـsingle-domain baseline وtarget-history وnull وOOS وcalibration. لا تبدأ قبل وجود Evidence Library كافية.

### 8.7 `Research Runtime`

مسار معزول يعيد تشغيل patterns البحثية على بيانات لاحقة ويصدر alerts قابلة للتدقيق. لا يرسل قرارات إنتاجية ولا يعدل المنصة الأم.

### 8.8 `Runtime Compatibility`

طبقة توافق منفصلة إن تقرر لاحقاً أن artifact علمياً يحقق بوابات الترقية. يجب أن تحافظ على scientific classification وuncertainty وfailure cases وevidence refs، ولا تستبدلها بإشارة مبسطة.

## 9. حالات الدليل المنهجية

| الحالة | المعنى | ما الذي تسمح به | ما الذي تمنعه |
|---|---|---|---|
| `candidate` | فرضية أو edge لم تكتمل أدلتها | استمرار الاختبار وفق عقد | اعتباره نجاحاً |
| `supported_predictive` | اجتاز البوابات المحددة في عقد predictive | إدخاله في Evidence Library وفق النطاق | causal أو production promotion تلقائياً |
| `provisionally_supported_descriptive` | تكرار وصفي أو predictive أولي واعد لكنه غير كافٍ | حفظه كمرشح بحثي | إدخاله كقاعدة تشغيلية أو وزن موجب دون مراجعة |
| `rejected` | فشل تحت العقد الحالية أو لم يضف قيمة | حفظ failure evidence وإعادة النظر بعقد جديدة فقط | إعادة تسويقه كنجاح |
| `unresolved` | نتائج متعارضة أو غير حاسمة | حفظ التفسيرات المتنافسة | ترجيح رواية بلا دليل |
| `not_testable` | البيانات أو المحاذاة أو ontology غير كافية للاختبار | تحديد ما ينقص | ملء الفجوة ببيانات مصطنعة |
| `suppressed` | artifact موجود لكن محجوب مؤقتاً عن الإصدار البحثي أو runtime | الاحتفاظ به للمراجعة | استخدامه كإنذار |
| `expired` | انتهت صلاحية artifact أو تغطيته الزمنية | حفظ التاريخ والسبب | تمديده بصمت |

`provisionally_supported_descriptive` ليست مرادفاً لـ`supported_predictive`، و`supported_predictive` ليست مرادفاً لـ`causal`.

## 10. سجل المصطلحات متعددة المعنى أو المتضاربة

### 10.1 `State` مقابل `Outcome`

| السياق | المعنى المقصود | مثال CHAOS | ما لا يعنيه |
|---|---|---|---|
| `current state` | حالة قابلة للإصدار من بيانات `t` أو قبلها | `high_growth` عند `t` | ليست نتيجة `t+3` |
| `target/outcome state` | حالة نتحقق منها بعد الأفق | `material_deterioration` عند `t+3` | لا يجوز استخدامها لتعريف state الحالية |

### 10.2 `Event` مقابل `Shock`

| السياق | المعنى المقصود | مثال |
|---|---|---|
| `event` | الواقعة المصدرية المؤرخة | زلزال USGS أو بلاغ WHO |
| `shock` | أثر مشتق يحتاج قياساً أو عقداً | اضطراب الإنتاج بعد الحدث |

التضارب الذي يجب منعه هو كتابة `earthquake = production_shock` أو `COVID event = annual economic shock` دون قياس ومحاذاة.

### 10.3 `Regime` بمعنيين مختلفين

| السياق | المعنى المقصود |
|---|---|
| اقتصادي/طاقي | نطاق من القياسات أو القيود مثل `high_growth` أو `energy_stress` |
| سياسي/مؤسسي | نظام أو ترتيب مؤسسي؛ لا يستخدم تلقائياً كـfeature عددي |

في الوثائق يجب كتابة `economic regime` أو `institutional regime` عند احتمال الالتباس.

### 10.4 `Probability` بثلاثة استعمالات

| التعبير | المعنى الصحيح |
|---|---|
| `regime_probability` | ثقة أداة تصنيف الحالة وفق ملاحظاتها |
| `transition probability` | مخرج نموذج انتقال بين حالات وفق عقده |
| `event/outcome probability` | احتمال ناتج عن نموذج outcome محدد |

لا يجوز قراءة أي واحد منها كاحتمال سببي أو كاحتمال حقيقي مطلق من دون تصميم يبرره.

### 10.5 `Weight` بثلاثة استعمالات

| التعبير | المعنى الصحيح |
|---|---|
| `feature weight` | وزن داخلي أو أهمية في نموذج استكشافي |
| `path/composer weight` | مساهمة محسوبة لمسار داخل صيغة تركيبية |
| `evidence weight` | أولوية أو درجة حوكمة مبنية على الأدلة |

هذه الأوزان ليست متبادلة، ولا يجوز تحويل feature importance إلى causal coefficient أو تحويل composer weight إلى حقيقة تاريخية.

### 10.6 `Baseline` بمعنيين شائعين

| السياق | المعنى |
|---|---|
| `statistical baseline` | نموذج مقارنة بسيط مثل prevalence أو persistence |
| `historical baseline` | مرجع زمني أو مستوى سابق لتعريف shock أو recovery |

يجب تحديد النوع عند استعمال كلمة baseline؛ فالأول يقارن الأداء، والثاني يعرّف الأثر أو التعافي.

### 10.7 `Null` بمعنيين

| السياق | المعنى |
|---|---|
| `null control` | تصميم عشوائي أو shifted reference لاختبار الفرق عن الصدفة |
| `null / missing value` | خانة لا تحتوي قيمة |

لا يجوز تفسير missing value على أنها null hypothesis، ولا تفسير p-value من null control على أنها احتمال صحة الفرضية.

### 10.8 `Source` مقابل `Source State`

`source` قد يعني مزود البيانات أو الملف، بينما `source_state` يعني العقدة الابتدائية في edge. يجب استخدام `source_id` للمصدر الخارجي و`source_state` للحالة حتى لا تختلط provenance ببنية المسار.

### 10.9 `Target` مقابل `Target History`

`target` قد يعني outcome المراد التنبؤ به، بينما `target history` يعني القيم السابقة لهذا outcome المستخدمة كمدخل. استخدام target history لا يعني تسريباً إذا كان متاحاً قبل زمن التنبؤ، لكنه يجب أن يظهر كbaseline أو feature group منفصل.

### 10.10 `Runtime` بمعنيين

| السياق | المعنى |
|---|---|
| `Research Runtime` | إعادة تشغيل بحثية معزولة، alerts وevidence فقط |
| `Production/runtime compatibility` | قدرة نظام خارجي على استهلاك artifact واتخاذ أو تمرير قرار |

وجود Research Runtime لا يعني أن pattern أصبح production-ready.

### 10.11 `Validation` بمعنيين محتملين

| السياق | المعنى |
|---|---|
| `validation split` | جزء زمني يستخدم للتقييم أو الاختيار وفق العقد |
| `data validation` | فحص schema أو coverage أو types أو provenance |

لا يجوز الخلط بين نجاح فحص schema ونجاح predictive validation.

### 10.12 `Discovery` مقابل `Confirmation`

`discovery` هو فتح فضاء بحث أو العثور على مرشح، أما `confirmation` فهو اختبار لاحق مجمد لا يجوز اختيار القاعدة منه. نجاح discovery لا يكفي للترقية.

### 10.13 `Independent` مقابل `External`

`independent source` يعني مصدراً أو لوحة مختلفة عن مصدر اكتشاف النمط ضمن درجة الاستقلال المحددة. `external` يعني خارج النظام أو المصدر الحالي، لكنه ليس بالضرورة مستقلاً منهجياً؛ قد يشترك في نفس upstream أو التعريف.

### 10.14 `Coverage` مقابل `Completeness`

`coverage` تصف ما هو موجود فعلياً، أما `completeness` فهي حكم مقيد بقاعدة محددة، مثل اكتمال 25 سنة لكل 11 متغيراً لكل كيان. لا يجوز تحويل coverage الجزئية إلى completeness عامة.

### 10.15 `Observed` مقابل `Derived`

`observed` قيمة أو سجل كما جاء من المصدر، بينما `derived` ناتج قاعدة أو محاذاة أو تصنيف. يجب ألا يُكتب derived فوق observed، ويجب أن يحتفظ derived بمرجع إلى observed والعقد الذي أنتجه.

## 11. قواعد تسمية عملية

ينبغي أن يوضح اسم كل artifact معناه ومجاله وتواتره وإصداره، مثلاً:

```text
AMA_HIGH_GROWTH_STATE_V1
AMA_MATERIAL_DROP_2PP_T_PLUS_3_V1
USGS_EARTHQUAKE_DOMAIN_STATES_EVENT_V1
WHO_COVID_DOMAIN_STATES_DAILY_V1
ECONOMIC_DETERIORATION_TO_UCDP_CONFLICT_V1
```

يجب تجنب أسماء عامة مثل `risk`, `impact`, `pressure`, `signal`, أو `probability` دون domain وdefinition وtime semantics. إذا كان المصطلح ضرورياً لكنه متعدد المعنى، يُضاف qualifier واضح مثل `economic_`, `institutional_`, `event_`, `reported_`, `future_`, أو `runtime_`.

## 12. قواعد لا يجوز كسرها

1. لا يُستخدم `Pattern` كمرادف للنجاح.
2. لا يُستخدم `Edge` كمرادف للسببية.
3. لا يُستخدم `State` لاحتواء outcome مستقبلي.
4. لا يُستخدم `Event` كمرادف لـshock أو production loss.
5. لا يُستخدم `Probability` كمرادف للاحتمال السببي.
6. لا تدخل الحواف `rejected` أو `unresolved` أو `not_testable` بوزن موجب.
7. لا تتحول feature importance أو attention إلى mechanism.
8. لا يُحوّل daily أو event إلى annual دون alignment contract.
9. لا تُستبدل missing values بأصفار أو تخمينات بلا عقد.
10. لا تُدمج المصادر المتعارضة قسراً.
11. لا تُستخدم أسماء القادة أو الأحزاب كمتغيرات سببية افتراضية.
12. لا يتغير تعريف المصطلح بصمت؛ أي تعديل جوهري يضاف كإصدار جديد أو سجل تغيير.

## 13. سجل التغييرات

| الإصدار | التاريخ | التغيير |
|---|---|---|
| V1 | 2026-08-26 | إنشاء القاموس الأساسي، العلاقات الهرمية، حالات الدليل، وسجل المصطلحات متعددة المعنى |

> عند إضافة مجال أو adapter أو family جديدة، يجب تحديث هذا الملف إذا أدخلت مفردات جديدة أو معنى جديداً لمصطلح قائم، مع تسجيل التغيير في هذا الجدول.
