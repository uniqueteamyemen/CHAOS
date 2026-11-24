# P2 — سجل الإغلاق المرحلي

**الفرع المرجعي:** `main-phase2`  
**Commit التشغيل الإنتاجي:** `72edc44b183e0c7c92e1edae362426d189e0c886`  
**Workflow:** [#45244943216](https://github.com/uniqueteamyemen/CHAOS/actions/runs/45244943216) — success  
**Release:** [p2-phase-close-v1.0](https://github.com/uniqueteamyemen/CHAOS/releases/tag/p2-phase-close-v1.0)  
**الحالة الحالية:** اكتمل التشغيل الإنتاجي الهندسي لجميع 519 مرشحاً والتحقق من تجميعها؛ لم يكتمل الاعتماد العلمي لـP2 ولا اعتماد null الزلزالي.

## 1. نطاق التغييرات

1. **نزاهة كتالوج USGS:** إعادة فحص الإحداثيات والمقدار والزمن، دعم antimeridian، حفظ المصدر الخام وبصمته، حجر السجلات المخالفة، حفظ `magType` و`magSource`، ومصالحة عدد المستلم والمقبول والمحجور والمكرر.
2. **فصل الكاشف عن أهلية null:** تشغيل `BreakDetectorV1` على السلسلة المرصودة أولاً؛ ثم تقييم أهلية نموذج العدم بشكل مستقل. فشل G1 لا يمنع إصدار نتيجة الكاشف.
3. **Null اقتصادي/سلعي:** يُستخدم Stationary Bootstrap للمستوى عند اجتياز فحص المستوى. عند فشله، يجري فحص الفروق الأولى؛ وإذا اجتازت الفروق الفحص، يُستخدم bootstrap للفروق مع إعادة تكوين مسار المستوى. إذا فشل الفحصان، لا يُنشأ بديل اصطناعي ولا تُحسب احتمالية إنذار.
4. **Null زلزالي:** يُمنع استخدام Stationary Bootstrap العام على سلاسل الزلازل. تُسجل الحالة `SKIPPED_DOMAIN_NULL_REQUIRED` إلى أن يتوفر كتالوج مكتمل ومقياس magnitude متجانس/معاير ونموذج point-process مناسب.
5. **Markov diagnostics وPR gate:** إدراج أدوات قراءة manifest وتحليل السلوك والقوة تحت تغييرات محقونة، مع فحوص تعاقدية وبوابة PR لتشغيل الاختبارات والتحقق المحدود الحي ورفع artifacts.

## 2. حدود الاستنتاج

- ADF/KPSS فحوص تمهيدية للأهلية، وليست برهاناً على صحة النموذج أو السكون الصارم.
- Integrated bootstrap للفروق الأولى هو null شرطي استكشافي لسلاسل اقتصادية/سلعية مرشحة لحالة I(1)، وليس اختياراً نهائياً أو صالحاً تلقائياً لكل سلسلة غير ساكنة.
- الاحتمال الناتج من أي bootstrap هنا **احتمال إنذار شرطي تحت نموذج العدم المحدد**، وليس FPR تشغيلياً مثبتاً بحقيقة أرضية.
- Gardner–Knopoff أداة تصنيف/حساسية تجريبية؛ لا تُنقل معايرتها الإقليمية تلقائياً إلى أحزمة USGS الحالية.
- لا يوجد في هذا الإغلاق اعتماد لـ`Mc(t,region)` أو ETAS/Hawkes أو inhomogeneous Poisson كنموذج زلزالي صالح. عقد الزلازل يظل `design_contract_not_yet_validated` حتى تنجح اختبارات الملاءمة خارج العينة.
- لا توجد هنا دعوى تنبؤ زلزالي أو إنذار تشغيلي أو سببية.

## 3. حدود الحماية

- لا تعديل لـ`structural_engine/isolated_break_detector_v1/**`.
- لا تعديل لـ`experiments/**`.
- لا تغيير في عتبة Markov المجمدة أو ثوابته.
- تبقى `discovery/cross-series-volatility-v1` خارج هذا الإغلاق؛ نتائجها مرشحات وصفية candidate-only بلا null/p-values/FDR أو أهلية point-in-time.

## 4. معايير إغلاق بوابة التنفيذ

يجب أن ينجح PR في:

1. اختبارات العقود ووظائف USGS ومصالحة السجلات.
2. اختبارات فصل تنفيذ الكاشف عن أهلية null، ومسارات المستوى والفروق الأولى ومنع null عام للزلازل.
3. اختبارات Markov diagnostics وحقن التغيرات والقدرة/التأخير.
4. اختبارات عقد الزلازل وأداة declustering.
5. تشغيل حي محدود لـP2.2، ثم تدقيق manifest، ثم مخرجات Markov والزلازل المحفوظة كـartifacts.
6. فحص immutability ضد `main-phase2`.

نجاح هذه البوابة يعني أن حزمة التنفيذ اجتازت اختبارات البرمجيات والتدقيق المحدد في هذا PR. لا يحوّل ذلك عقود البحث غير المتحققة إلى نتائج علمية معتمدة.


## 5. تحديث الحالة بعد دمج PR #36 — 2026-11-24

رأس `main-phase2` الحالي عند استعادة MP0 هو `72edc44b183e0c7c92e1edae362426d189e0c886`. دُمج PR #36 (`feat(P2): deterministic three-stage production stress pipeline`) في هذا الرأس.

- أصبحت مراحل `prepare → evaluate → aggregate-and-audit` جزءاً من `main-phase2` عبر `real_data_stress_pipeline/production_pipeline.py`.
- السجل المخطط يضم 519 مرشحاً: 51 Pink Sheet و468 GEM/USGS؛ تحفظ Pink Sheet الخام في الذاكرة داخل prepare، وتوزع السلاسل الأخرى في أربعة shards حتمية، ثم يتحقق aggregate من العضوية والترتيب والبصمات.
- PR gate في تشغيل PR #36 نجح، لكن وظائف prepare/evaluate/aggregate والتدقيقات والنشر كانت skipped على حدث PR. لذلك لا يُستخدم نجاح gate كدليل تشغيل إنتاجي كامل.
- في الأدلة التي تمت مراجعتها لهذا التحديث لم يثبت بعد تشغيل كامل ناجح على `main-phase2@72edc44` مع artifacts نهائية لجميع المراحل. حالة التنفيذ الإنتاجي لذلك الرأس: `NOT_YET_VERIFIED`، وليست `SUCCESS` أو `FAILED`.
- لا يُعلن إغلاق P2 علمياً بمجرد دمج pipeline. يبقى كل cohort مرتبطاً ببوابته وقياساته، ولا تتحول احتمالات الإنذار الشرطية من bootstrap إلى FPR تلقائياً.

### قرار تقدم الأفواج

نقص أصول WGI/WHO/IMF لا يوقف P2 المستقل على Pink Sheet وGEM وUSGS. يسجل كل مصدر أو vintage غير متاح `UNKNOWN` ولا يُختلق. يستمر USGS في catalog integrity وdetector diagnostics، مع بقاء الاعتماد الإحصائي للـseismic null وFPR معلقاً حتى إثبات completeness و`Mc(t,region)` وpoint-process null. لا يستخدم stationary bootstrap العام للزلازل.

هذا تحديث لحالة التنفيذ، ولا يغير الكاشف المجمد أو `experiments/**`، ولا يجيز Engine 2 قبل D6.


## 6. إثبات التشغيل الإنتاجي الكامل — 2026-11-23

تم التحقق مباشرة من GitHub Actions run `45244943216` على `main-phase2@72edc44...`:

- `prepare`: success.
- `evaluate (0..3)`: نجاح shards الأربعة.
- `aggregate-and-audit`: success.
- `audit-domain-null`: success.
- `audit-markov-real-data`: success.
- `audit-markov-injected-break`: success.
- `stage-phase-close-release` و`publish-phase-close`: success.
- `pr-gate`: skipped لأنه تشغيل push، وليس PR.

### سلامة خط الإنتاج

| القياس | القيمة |
|---|---:|
| مرشحو Pink Sheet | 51 |
| مرشحو GEM | 458 |
| تمثيلات USGS | 10 |
| إجمالي المرشحين | 519 |
| عدد الـshards | 4 |
| نتائج تم التحقق منها | 519/519 |
| نتائج مفقودة | 0 |
| نتائج مكررة | 0 |
| أخطاء جلب المصدر | 0 |
| زمن prepare | 3,533.087 ثانية |
| زمن aggregate | 1.626 ثانية |

استعاد aggregate الترتيب الأصلي للمرشحين قبل إنتاج manifest. بقيت قيم Pink Sheet الخام في الذاكرة في مهمة prepare ولم تُكتب إلى artifacts. تم التحقق من 31 ملف مصدر خام محفوظ، مع بصمات المخرجات والمدخلات.

- Manifest SHA-256: `aed50955a8e513bb62db4ee423d552801dfe76de14d85554d4d65471546ebe51`.
- Checksums SHA-256: `1aa9d976f81cc9166cea21b46fac8a0c75721dd3a960a9a7f170e33b7a341cda`.
- نُشر الإصدار `p2-phase-close-v1.0` موجهاً إلى commit `72edc44...`، وتم التحقق من 11 remote release assets مع تطابق البصمات والأحجام.

### 6.1 تأهيل G1 وأهلية null — فصل إلزامي

| الفوج | السلاسل | اجتازت G1 | null مؤهل | null متروك |
|---|---:|---:|---:|---:|
| Pink Sheet / strict long monthly | 51 | 48 | 48 | 3 |
| GEM / secondary monthly | 458 | 311 | 311 | 147 |
| USGS / monthly counts | 5 | 1 | 0 | 5 |
| USGS / event inter-arrival | 5 | 1 | 0 | 5 |
| **الإجمالي** | **519** | **361** | **359** | **160** |

من الـ160 التي لم تحصل على null:
- 158 لم تجتز G1 (150 في Pink/GEM و8 في تمثيلات USGS).
- تمثيلان زلزاليان اجتازا G1، لكن null العام ما زال ممنوعاً عليهما لأن null زلزالياً من نوع point-process لم يُعتمد.

هذا الفصل مقصود: الكاشف عمل على الـ519 سلسلة بعد اجتياز بوابات جودة الإدخال/الطول، بينما أهلية null تم تقييمها بشكل مستقل. نجاح الـ519/519 يعني اكتمال التنفيذ والتجميع، لا اجتياز 519 نموذج عدم.

### 6.2 الاستبعادات قبل تكوين 519 مرشحاً

سجل manifest يحوي 22 حالة رفض في مرحلة المصدر/الجودة، وليست 22 سلسلة إضافية ضمن الـ519:
- 20 سلسلة Pink Sheet: 12 لقصر التاريخ، و6 لتدهور MAD للفروق، و2 لتدهور MAD للمستوى.
- سلسلة GEM واحدة لعدم كفاية المشاهدات.
- حدث USGS واحد من Sunda–Andaman تم حجره لأسباب تشمل وقوعه خارج حدود الحزام وبأقل من حد المقدار المطلوب.

لم تُسجل أخطاء جلب مصادر. الحدث المحجور بقي موثقاً في بيانات الرفض ولم يدخل كتالوج التحليل.

## 7. النتائج حسب الفوج

احتمالات الإنذار أدناه هي متوسط احتمال صدور إنذار واحد أو أكثر في Stationary Bootstrap الشرطي لكل سلسلة اجتازت G1. ليست FPR تشغيلية، ولا تُجمع الأفواج معاً.

| الفوج | الوضع | إنذارات مرصودة | null مؤهل | متوسط احتمال الإنذار الشرطي |
|---|---|---:|---:|---:|
| Pink Sheet | Fast | 7 | 48 | 7.68% |
| Pink Sheet | Markov CUSUM | 62 | 48 | 35.98% |
| Pink Sheet | Consensus | 0 | 48 | 1.08% |
| GEM | Fast | 165 | 311 | 8.71% |
| GEM | Markov CUSUM | 594 | 311 | 27.75% |
| GEM | Consensus | 46 | 311 | 2.02% |
| USGS / event inter-arrival | Fast / Markov / Consensus | 213 / 649 / 74 | 0 | لا يوجد |
| USGS / monthly counts | Fast / Markov / Consensus | 5 / 5 / 2 | 0 | لا يوجد |

القراءة:
- Markov أصدر إنذارات أكثر بكثير من Fast في Pink Sheet وGEM، مع احتمالات إنذار شرطية مرتفعة نسبياً تحت نماذج null الحالية.
- Consensus شديد التحفظ، لكنه لا يصبح الأفضل بمجرد انخفاض الإنذارات؛ يلزم قياس الحساسية والفقد والتأخير ومقارنة عادلة.
- أرقام الزلازل وصفية لسلاسل مرصودة، ولا يوجد null مؤهل يسمح بتقدير احتمال إنذار شرطي لها.

### 7.1 مطابقة مراسي تاريخية محددة

المطابقة واحد لواحد ضمن نافذة ±12 شهراً، وهي اختبار استرجاعي محدود لمراسي سياقية وليست إثبات تنبؤ/سببية:

- GFC 2008: Markov 32/509 مطابقات؛ 20 قبل المرساة، 2 في الشهر نفسه، 10 بعدها؛ وسيط lead = 2.5 شهر.
- COVID 2020: Markov 41/509؛ 22 قبل المرساة و19 بعدها؛ وسيط lead = شهر واحد.
- Fast: 18/509 عند GFC و8/509 عند COVID؛ أغلبها بعد المرساة.
- Consensus: 3/509 عند GFC و0/509 عند COVID.
- Oil 2014 وUkraine 2022 لهما أفواج أصغر جداً؛ لا تُقارن نسبهما مباشرة بالأفواج العامة.

لا يثبت هذا أن القيمة كانت منشورة ومتاحة في الزمن الفعلي عند صدور الإشارة؛ ويتطلب ذلك source vintages ذات `available_at` موثق.

## 8. تدقيق USGS والـdomain-specific null

نجح مصدر USGS ونجح integrity gate للأحزمة الخمسة. مجموع الأحداث المقبولة 94,730 من 94,731 حدثاً مستلماً؛ حدث واحد حُجر في Sunda–Andaman.

| الحزام | أحداث مقبولة | Integrity |
|---|---:|---|
| Japan–Kuril–Kamchatka | 21,691 | PASS |
| Sunda–Andaman | 45,546 | PASS_WITH_QUARANTINE |
| Andes subduction | 18,074 | PASS |
| Alaska–Aleutian | 6,400 | PASS |
| Hellenic–Anatolian | 3,019 | PASS |

لكن تدقيق null الزلزالي أبقى:
- `catalog_completeness = NOT_ASSESSED`.
- كل أحداث الأحزمة الخمسة تفتقد `magnitude source` في بيانات الاستيراد.
- أنواع المقدار heterogeneous في كل حزام، ولا ينجح precheck لنوع مقدار واحد.
- حد الاستعلام M≥4.5 ليس تقديراً لـ`Mc(t,region)`.
- Gardner–Knopoff يبقى sensitivity method غير متحقق محلياً لهذه الأحزمة.
- محاكاة homogeneous Poisson هي benchmark استكشافي، لا null معتمداً ولا FPR.
- لا قبول لـETAS/Hawkes أو inhomogeneous Poisson، ولا ادعاء إنذار زلزالي/تنبؤ.

إذن USGS اجتاز سلامة استيراد/كتالوج محددة، لكنه لم يجتز بعد بوابة completeness/null اللازمة لأي اعتماد إحصائي زلزالي.

## 9. تدقيق Markov على Pink Sheet

### 9.1 سلوك البيانات الحقيقية

اكتمل audit على 51 سلسلة Pink Sheet؛ 48 مؤهلة لـG1، و191,808 سجل إعادة توليد. قورنت مدخلات raw مع rolling-MAD scale-only من دون تعديل `BreakDetectorV1`.

في السلاسل الأطول، لم يظهر انخفاض عام متسق في احتمالات الإنذار الشرطية عبر الفئات:
- agriculture_food: 31.97% raw مقابل 32.35% rolling-MAD.
- energy (539 observations): 42.52% مقابل 40.32%، مع عينة 5 سلاسل فقط.
- metals: 39.80% مقابل 40.48%.
- other_commodity: 38.90% مقابل 37.69%.

النتائج متباينة بحسب الفوج؛ لا تثبت أن rolling-MAD تحسين عام أو أن Markov صار معايراً.

### 9.2 حقن تغيرات controlled

اكتمل اختبار 383,616 replicate record على السلاسل المؤهلة، باستخدام:
- `mean_shift_2_5_initial_MAD`
- `volatility_jump_2x`
- طول 100 مشاهدة وعينة التاريخ الكامل (515/539 مشاهدة بحسب السلسلة).
- raw مقابل rolling-MAD scale-only.

في اختبارات mean-shift الطويلة ظلت معدلات clean detection متقاربة بين raw وrolling-MAD، وكذلك التأخير الوسيط تقريباً. أما volatility jump فزاد rolling-MAD معدل الكشف النظيف في الفئات الأربع، لكن زاد أيضاً median detection delay:
- agriculture_food: clean detection 6.74% → 10.76%، والتأخير 70.0 → 84.48 مشاهدة.
- energy: 8.39% → 12.21%، والتأخير 69.9 → 84.6.
- metals: 8.34% → 12.68%، والتأخير 66.57 → 83.64.
- other_commodity: 7.76% → 10.69%، والتأخير 68.45 → 78.59.

هذه اختبارات حقن داخل عينات تاريخية، وليست قياسات تشغيلية خارج العينة أو FPR. كما أن pre-break alarm probability في الأطوال الكاملة بقي مرتفعاً نسبياً في عدة أفواج؛ فلا يجوز اعتماد التحسن في post-break probability بمعزل عن الإنذارات السابقة والتأخير.

**قرار التدقيق:** rolling-MAD scale-only يبقى تشخيصاً/مرشحاً، لا تغييراً مقبولاً في detector ولا حلاً عاماً لمشكلة Markov.

## 10. قرار المرحلة

<badge color="success">إغلاق هندسي للتشغيل الإنتاجي</badge> <badge color="warning">الاعتماد العلمي ما زال مفتوحاً</badge>

1. اكتمل تشغيل pipeline P2.2 على 519 مرشحاً مع تحقق كامل للـshards والتجميع والنشر.
2. اكتمل تدقيق Markov وحقن التغيرات وتدقيق domain-null بوصفها مخرجات بحثية محددة.
3. يبقى P2 مفتوحاً علمياً؛ فلا توجد حتى الآن مصفوفة اعتماد مكتملة لكل cohort تشمل false alarms/decade أو ARL0 المناسب، conditional detection delay، miss rate، FDR/alpha-spending، coverage/abstention وفواصل الثقة.
4. USGS يحتاج استكمال magnitude provenance و`Mc(t,region)` وpoint-process null؛ لا يُمنع استمرار catalog integrity أو التحليل الوصفي.
5. Pink Sheet/GEM يستطيعان مواصلة المنافسة/المعايرة على cohort-specific null المؤهل، دون ادعاء operational FPR.
6. لا تعديل على الكاشف المجمد أو `experiments/**`; لا Engine 2 قبل اعتماد D6.

## 11. أثر المصدر والـartifacts

- GitHub Actions run: [45244943216](https://github.com/uniqueteamyemen/CHAOS/actions/runs/45244943216)
- Release: [p2-phase-close-v1.0](https://github.com/uniqueteamyemen/CHAOS/releases/tag/p2-phase-close-v1.0)
- Release target: `72edc44b183e0c7c92e1edae362426d189e0c886`.
- Manifest SHA-256: `aed50955a8e513bb62db4ee423d552801dfe76de14d85554d4d65471546ebe51`.
- Aggregate artifact SHA-256: `e84a4cb7aa0af8576b21803b38eea321ca7b307ba9290c23ea154f56f06ca5e5`.
- Domain-null artifact SHA-256: `5f5b0c571c1423caef4cfc9001271c8bea261f1b89e2ba0a341f733f677ed683`.
- Markov real-data artifact SHA-256: `84748d2a38581bafcb0ac8e3a131967cd9fcddb4c649ea7ab2dda38e8041b43c`.
- Markov injected-power artifact SHA-256: `131a7735f43a40cca109ac38893f30436b67d355d3c50ae1194b82cbd21e38b8`.
