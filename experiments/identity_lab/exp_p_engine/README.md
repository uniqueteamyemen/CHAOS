# exp_p_engine — المحرك الموحّد

> **آخر تحديث: 2026-11-15 (+03:00)**

## ما هو

خط أنابيب واحد يجمع كل ما بُني وبقي صالحاً:

```
بُقيا الهوية
  → خط أساس: انحياز مجمّد + مقياس ضجيج متحرك؛ P1 يستخدم سقفاً، وCUSUM يعمل بمقياس متحرك ويُعلّق عند اكتشاف تغير في نظام الضجيج
  → كواشف: sign-run (P1، σ بسقف 2× الهادئ) و CUSUM (P2، σ متحرك ويُعلّق أثناء حالة الضجيج المرتفع)
  → عدّاد: sign-run break counter (P3)
  → مدير إنذارات: أولوية، كتم P1 محصور بالكيان، تهدئة؛ CUSUM يعيد التصفير تلقائياً بعد إطلاق الإنذار
```

## القرارات المبنية (ولماذا)

| القرار | السبب |
|---|---|
| **فصل مقياس P1 عن P2** | P1 يستخدم σ متحركة بسقف 2× σ الهادئ لحماية التسرب الكبير من ابتلاع الضجيج؛ عندما يتجاوز تقدير الضجيج على نافذة 12 نقطة عتبة 1.5× σ الهادئة، يتحول P1 إلى اختبار اتجاهي يتطلب 13 إشارة متتالية من العلامة نفسها، ويُعلّق CUSUM ويُصفّر مؤقتاً فقط عندما تتجاوز σ القصيرة (12 نقطة) σ الطويلة (52 نقطة) بنسبة 20%، ثم يستأنف بعد استقرار التباين. تُعلن المنظومة حالة degraded؛ وقد تبقى التسربات الصغيرة غير محسومة أثناءها. |
| **نافذة هدوء إلزامية** | حساب الانحياز على كل السلسلة يبتلع التسرب. المحرك يرفض التشغيل بلا نافذة هدوء أو بنقاط غير كافية. |
| **لا STL** | F=1.21 على بُقيا EIA → الموسمية تتساقط جبرياً في طرح طرفي الهوية. |
| **CUSUM تجميعي** | يلتقط الانحرافات الصغيرة المستمرة عندما تتجاوز حساسيته؛ يجب قياس الإنذار الكاذب خارج العينة لكل هوية ومجال قبل التشغيل. |
| **عدّاد sign-run فقط (P3)** | يقيس تكرار كسور sign-run فقط. CUSUM مصدر إنذار مستقل ولا يُدمج قبل اختبار إزالة تكرار موثوق. |
| **كتم P1 محصور بالكيان** | كتم شامل يخفي تسرباً ثانياً مستقلاً. |
| **تصفير CUSUM** | التنفيذ الحالي يعيد التصفير تلقائياً عند إطلاق إنذار؛ لا توجد آلية تأكيد مشغّل في هذه النسخة. |

## الاختبارات

تشمل الاختبارات رفض Sigma هادئة صفرية، وقياس الإنذارات الكاذبة مع الضجيج المتزايد بلا تسرب، واختبار التسرب المتدرج.

- بلا تسرب → صامت.
- تسرب ثابت → P1.
- تسرب صغير (2/شهر) → P2 فقط (CUSUM).
- P1 يكتم P2 لنفس الكيان.
- التهدئة تمنع التكرار.
- تدفق نقدي → نفس السلوك (مجال ثانٍ).
- **الانحياز المجمّد لا يبتلع تسرباً مستمراً**.
- **الضجيج المتزايد بلا تسرب**: يجب أن يُعلن degraded ويوقف CUSUM، مع إبقاء اختبار الاتجاه P1؛ اختبار 40 بذرة يفرض معدل إنذار كاذب لا يتجاوز 10%.
- **نافذة الهدوء إلزامية**، والنقاط غير الكافية تُرفض.
- `adapt` يربط أسماء الأعمدة بالحقول القانونية لهوية حفظ عددية؛ يجب أن تكون القيم العددية وعمود الزمن متوافقة مع عمليات المحرك.

## النطاق والحدود

- **يشمل**: هويات حفظ عددية (مخزون، تدفق نقدي).
- **لا يشمل**: هويات منطقية/عقدية (PayLock H1 — وحدة `exp_a` منفصلة).
- **حدود معلنة**: لا إسناد بلا تسجيل ثانٍ؛ لا كشف مضموناً تحت حساسية الكواشف؛ سقف Sigma يوازن بين عدم ابتلاع الانحراف وزيادة الإنذارات عند تغير الضجيج.

## تكييف المدخلات — عقد صريح للبيانات القادمة

`adapt(rows, mapping)` محوّل أسماء أعمدة إلى الحقول القانونية (`opening`/`inflow`/`outflow`/`other`/`closing`) لهوية حفظ عددية. لا يحوّل أنواعاً اعتباطية ولا يزيل شروط صلاحية الزمن والقيم العددية.

- مصدر جديد متوافق = **mapping جديد**، لا إعادة كتابة للمحرك.
- الحدود الاختيارية (`other`) تفترض صفراً عند غيابها.
- يجب أن يحدد العقد أعمدة عددية متوافقة وعمود زمن قابل للمقارنة الحسابية.

## التشغيل

```bash
python -m unittest experiments.identity_lab.exp_p_engine.test_engine -v
```


## المسار العام المحايد عن المجال — تجربة مستقلة

أضيفت طبقة منفصلة باسم domain_neutral.py. لم تتغير دالة engine.run() ولا engine.py؛ فهما ما زالا مسار هوية الحفظ العددية الحالي. المسار الجديد يستقبل قياسات عامة ولا يشترط أعمدة المخزون أو التدفق النقدي.

### عقد الإدخال الأدنى

الحقول الخمسة الإلزامية هي:

- entity_id
- metric_id
- event_time
- value
- observation_status

الوحدة، المجموعة، المصدر، إصدار المصدر، ومدى دعم الزمن بيانات اختيارية. غياب القيمة يُسجل missing ولا يتحول إلى صفر. لا يوجد forward-fill. الفترات المتوقعة التي لا يوجد لها سجل تبقى فجوات ظاهرة. تعريف العقد مضمّن في residual_event_v1.schema.json#/definitions/observation، بينما يظل عقد حدث الهوية القديم في جذر الملف كما هو.

### ما يعمل في هذه النسخة

- خط أساس أحادي السلسلة prequential باستخدام وسيط التاريخ السابق أو Theil-Sen الاتجاهي؛ لا تدخل الملاحظة الحالية في بناء مرجعيتها.
- مرشح First-Difference MAD. لا تُستخدم الفجوات الزمنية الأكبر من وحدة واحدة إلا عند توفر تقدير AR(1) مدعوم؛ وإلا تُستبعد الفروق غير المدعومة. كما لا تُحتسب أول ملاحظة بعد فجوة زمنية غير مرصودة كدليل كسر حتى تتوفر نقطة لاحقة متصلة.
- كاشف CUSUM ثنائي الاتجاه وP1 مستقلان؛ تُحفظ raw hits ولا يوجد دمج أحداث أو كبح تنبيهات في هذه النسخة.
- مقارنة الأقران تستخدم cohort_id صريحاً صالحاً للفترة ووحدات قياس متوافقة؛ وعند تفعيل التعرض تتطلب exposure وexposure_unit. لا يستنتج المحرك أقراناً أو مقاماً من تشابه الأسماء أو القيم.
- العلاقات الجزئية تستخدم build_partial_relation_residuals بعلاقة يصرح بها المستدعي، وملاحظات مزدوجة متزامنة، وانحدار Theil-Sen سابق للحدث؛ لا تُعامل العلاقة على أنها سببية أو قانون حفظ.
- missingness detector مستقل، لكنه يتطلب جدول فترات متوقعة صريحاً خاصاً بالكيان والمؤشر. لم يُشغّل على World Bank لأن snapshot لا يحدد جدول الاستحقاق لكل دولة.
- أدوات BH وقياس الإنذارات لكل 1,000 كيان-سنة موجودة، لكن BH لا يُطبّق إلا على قيم p صالحة يقدمها مسار معاير. عتبات الكواشف الحالية مرشحة وليست معايرة إنتاجية.

### البيانات الفعلية المضمنة

real_data_probe.py يشغّل المسار على ملف World Bank السنوي (2000–2024) وعلى كتالوج USGS للأحداث ذات المقدار 6.5 فأعلى. يعرض عدد نقاط التغطية، الفجوات، جاهزية تقدير المقياس، وraw hits، دون وصفها كإنذارات صحيحة أو خاطئة لأن ملفات المصدر لا تتضمن حقيقة مرجعية معتمدة للأحداث الشاذة.

مجلد WHO يحتوي manifest يذكر المصدر وعدد الصفوف، لكن ملف CSV الخام غير موجود في الفرع الذي فُحص؛ لذلك يعلن المشغل تخطيه ولا يحتسبه ضمن التشغيل الفعلي.

benchmark_50k_cohort.py اختبار ضغط اصطناعي لـ50,000 كيان عبر 10 فترات. يختبر زمن التنفيذ واستجابة مقارنة الأقران لحقن معروف فقط؛ ولا يُقدّم بوصفه بيانات موارد بشرية أو معايرة تشغيلية.

**الحالة:** تجربة منفصلة، غير موصولة بمسار الإنتاج، وعتباتها غير معتمدة حتى تنتهي المعايرة على سلاسل حقيقية متعددة الأنواع.


### تحسينات ما بعد تشغيل البيانات الفعلية

أظهرت مقارنة التشغيل الأول أن الوسيط المتحرك وحده ينتج عدداً كبيراً من raw hits على World Bank؛ لم نعتبرها كسوراً صحيحة أو خاطئة، بل أضفنا مرجعاً اتجاهياً Robust Trend (Theil-Sen) للمقارنة على المصدر نفسه وبالعتبات المرشحة نفسها. يظل rolling median متاحاً؛ ولا يُستبدل الافتراضي قبل قراءة المقارنة.

أضيف مسار مستقل لإشارات فقد البيانات. لا يعتبر غياب الصف فقداً إلا إذا قدم المصدر جدول الفترات المتوقعة صراحة. كما يستثني pending وnot_applicable من مقام التغطية. مخرجاته تصنف كتغير في جودة المصدر/الجمع، ولا تدخل كإشارة سلوك للكيان.

أضيف exposure اختياري مع وحدته. عند تفعيله في المقارنة بين الأقران، تتم مقارنة value/exposure لا إجمالي الأعداد. لا يُفعّل تلقائياً؛ ويجب أن يكون المقام ذا معنى تشغيلي موحد داخل المجموعة والفترة (مثل ساعات العمل الفعلية، لا ساعات الجدول الاسمية إذا لم تكن تمثل التعرض الحقيقي).

اختبار 50k المحدّث يقارن على المجموعة الاصطناعية ذاتها بين العد الخام والمعدل لكل ساعة، ويعلن الاختلاف في الإنذارات الكاذبة الاصطناعية. هذه تجربة تكشف خطأ عدم تسوية التعرض؛ ولا تمثل بيانات موارد بشرية حقيقية.


### العلاقات الجزئية بين المؤشرات (Partial Relationships)

أضيف builder مستقل باسم build_partial_relation_residuals. يجب أن يحدد المستدعي metric X وmetric Y وrelationship_id صراحة. يجمع فقط الملاحظات المتزامنة للكيان نفسه، ويستبعد الأزواج غير المكتملة دون تعويض. عند كل فترة تُقدّر علاقة Theil-Sen من الأزواج السابقة فقط، ثم يحسب انحراف Y الفعلي عن Y المتوقع عند قيمة X الحالية.

هذا مسار علاقة إحصائية معلنة، لا قانون حفظ ولا إثبات سببية. يرفض تغير وحدة أي مؤشر داخل السلسلة ما لم يُمثّل ذلك بإصدار/هوية مقياس جديدة. إذا لم يتغير X بما يسمح بتقدير ميل العلاقة، يُعلن relation_unidentifiable بدلاً من اختراع خط أساس.


### عقد المتبقيات الموحد وربط الكواشف

كل باني مرجعية — Univariate وPeer/Cohort وPartial Relation — يصدر الحقول الأساسية نفسها، ويُعرّف العقد في residual_event_v1.schema.json#/definitions/residual. الحد الأدنى هو هوية الكيان والمؤشر والزمن، القيمتان المرصودة والمتوقعة، المتبقي، الحالة، هوية وطريقة المرجعية، وعدد نقاط الدعم.

validate_residual_contract يرفض الهوية الفارغة، والحالة غير المعروفة، وعدد الدعم غير الصحيح، والقيم غير المنتهية، والمقاييس غير الموجبة، وأي اختلاف حسابي بين observed - expected وresidual. الصفوف التي لا يتوفر لها scale صالح تبقى موجودة بحالة غير ready ولا تدخل الكواشف.

تُقسّم الكواشف الصفوف بحسب (entity_id, metric_id, baseline_id) قبل تشغيل أي حالة تراكمية. لذلك لا يمكن أن تكمل إشارة موظف آخر أو مؤشر آخر أو مرجعية أخرى عداد CUSUM أو sign-run. تُرتب كل سلسلة زمنياً، ويُرفض تكرار الفترة داخل السلسلة. مخرجات الكواشف تحتفظ بهوية السلسلة والمرجعية.

مقياس Peer الحالي هو MAD قوي واحد لكل مجموعة وفترة، مع استبعاد الكيان من وسيط القيمة المتوقعة نفسه. إذا كان تشتت المجموعة صفراً، يخرج peer_scale_unavailable؛ لا يخترع المحرك حداً أدنى للمقياس. في هذه الحالة نحتاج إلى حد ضوضاء/دقة معلن للمؤشر قبل تحويل الفرق الخام إلى z-score.


## Isolated parallel-fusion experiment (A/B/C/D)

This experiment is isolated from the production engine.py; A remains the unchanged engine.run() result.

- **A:** current production execution path, including the current alert manager.
- **B:** P1 uses the capped 3-sigma / 3-run candidate rule; positive and negative CUSUM accumulators are independent; both accumulators are held (not erased) while the short/long variance-transition condition is active; CUSUM scale remains unbounded.
- **C:** same independent detector tracks; CUSUM scale is capped at 2 times quiet sigma and transition updates are damped by 0.35 instead of being erased or paused.
- **Fusion:** evidence is aggregated before event adjudication. A reversal or six consecutive calm observations opens a new event. Same-event directional cooldown marks a repeated notification but retains the underlying evidence.
- **D (isolated high-noise P1 arm):** uses exactly C's two-sided CUSUM and changes only P1's high-noise behavior to the production engine's adaptive-scale, 13-consecutive-direction rule. C vs D therefore isolates the P1 contribution while the CUSUM evidence is held identical.
- **E/F/G (CUSUM reset sweep):** retain adaptive P1, use unbounded two-sided CUSUM with both accumulators reset during variance transitions, and compare h=8.5, 10.5 and 12.5.
- **H–K (CUSUM hold sweep):** retain the same adaptive P1 and unbounded two-sided CUSUM, but preserve accumulators through variance transitions. G/H compare reset vs hold at h=12.5; J/K fill h=14.5/15.5; I tests h=16.5.
- **Independent paired confirmation:** this run uses a new seed range (2,000,000+) and reports exact two-sided McNemar tests versus A for false alarms, detection, and pre-onset false alerts on identical trial seeds.
- **EIA replay:** replays all nine arms over the archived 617-week five-series EIA identity residual and compares persistent +3σ/+6σ test-copy injections after a fixed 130-week adaptation horizon. Post-adaptation event counts now include events that began earlier but carry detector evidence after the cutoff. Historical counts are descriptive only; the EIA residual has no adjudicated anomaly labels.

Each run creates an immutable configuration/input snapshot with a SHA-256 input fingerprint, frozen bias, quiet sigma, configuration, code revision, and time range. Out-of-order and duplicate timestamps fail closed.

Run the experiment:

```bash
python -m unittest experiments.identity_lab.exp_p_engine.test_parallel_fusion -v
python -m experiments.identity_lab.exp_p_engine.benchmark_parallel_fusion
python -m experiments.identity_lab.exp_r_grade4.grade4_diagnostics
```

The benchmark runs 500 independent sequences per condition on a fresh seed range and scores false alerts in null scenarios and in the pre-onset interval. It reports detector-isolated P1/CUSUM rates, sensitivity, direction errors, delay, Wilson intervals, and exact paired McNemar p-values versus A. G/H isolate reset vs hold at h=12.5; J/K/I refine the hold threshold. No candidate replaces A unless paired results justify that decision.
