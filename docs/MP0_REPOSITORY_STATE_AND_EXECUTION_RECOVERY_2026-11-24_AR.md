# CHAOS — تقرير استعادة حالة المستودع وتنفيذ MP0

**التاريخ:** 2026-11-24  
**المستودع:** `uniqueteamyemen/CHAOS`  
**خط الأساس:** `main-phase2@72edc44b183e0c7c92e1edae362426d189e0c886`  
**الخطة الحاكمة:** `docs/CHAOS_EXECUTION_PLAN_V2_AR.md` — SHA `abfa4efd270dfa4a906e03d22cdf8fa40d37134a`  
**نطاق التقرير:** جرد الفروع الثلاثة، ما دُمج فعلياً، الفجوات المتبقية، واستقلال جاهزية الأفواج.

## 1. النتيجة التنفيذية

1. لا يوجد مبرر لدمج أي من الفروع الثلاثة المحددة كاملاً. كلها متباعدة عن الرأس الحالي بـ112 التزاماً، والمكونات الأساسية المطلوبة إما اندمجت بالفعل عبر PRs لاحقة أو أصبحت نسخاً أقدم من التنفيذ الجاري.
2. لا يُحذف أي فرع تاريخي. تبقى الفروع الثلاثة محفوظة، لكن تُزال من قائمة العمل النشط ما لم يظهر اختلاف فريد يستحق مراجعة مستقلة.
3. لا ينبغي أن يمنع نقص WGI/WHO/IMF أو غياب `available_at` التاريخي التقدم في P2 على Pink Sheet وGEM وUSGS. تُطبّق بوابة الأهلية على كل cohort ونموذج null بصورة مستقلة.
4. هذا لا يعني قبول كل النتائج علمياً: USGS يمكنه متابعة سلامة الكتالوج وتشغيل الكشف والتوصيف، لكن ادعاءات FPR واعتماد seismic null تبقى معلقة إلى أن تثبت completeness و`Mc(t,region)` وملاءمة point-process null.
5. D0/P0 لا يُعلن مغلقاً بعد. أداة الجرد كانت تسجل refs قديمة، ولم يكن D0 manifest محفوظاً كملف tracked على `main-phase2`. عالج هذا الفرع مرجعيات D0 وتغطية ملفات التنفيذ الحديثة، وسيصدر الـworkflow artifacts عند اختبار PR.

## 2. خط الأساس وحالة الفروع

المقارنة تمت مباشرة من GitHub مع `main-phase2@72edc44...`.

| الفرع | HEAD الحالي | Ahead / Behind | PR المرتبط | القرار |
|---|---|---:|---|---|
| `governance/p0-baseline-audit-v1` | `6fd7400a1c94` | 37 / 112 | #21 مغلق غير مدمج | لا cherry-pick؛ تم supersede وظيفياً عبر #28 |
| `fix/p2-2-3-gem-snapshot` | `995487aa394d` | 73 / 112 | لا PR مفتوح مرتبط | نسخة أقدم؛ لا تُدمج فوق P2 الحالي |
| `diag/markov-real-data-behavior` | `fd758a157aaa` | 21 / 112 | لا PR مفتوح مرتبط | الاحتفاظ كمرجع تشخيصي؛ فحص إضافاته الفريدة لاحقاً |

### 2.1 فرع الحوكمة

- PR #21 أُغلق دون دمج لأن مساره أصبح superseded.
- PR #28 دمج قاعدة الهوية ودورة الحياة وملفات D0 ذات الصلة إلى `main-phase2` عند `e0c13b41...`.
- ملفات الجرد الحالية موجودة على `main-phase2`: D0 builder، observation identity، lifecycle، schemas، workflow الخاص بـD0، واختبارات الأساس.
- القرار: لا نقل جديد من هذا الفرع في MP0. تحديث D0 builder الموجود على main هو الإجراء الصحيح.

### 2.2 فرع GEM / Domain Null / USGS

- المسار الحالي أحدث من النسخة الموجودة على الفرع القديم.
- PR #33 دمج حزمة P2: integrity للكتالوج، فصل detector execution عن null eligibility، null routing، والتدقيقات.
- PR #34 صحح return routing ونطاق PR gate.
- PR #35 عالج نتائج المراجعة الخاصة بفشل GEM وتوثيق الأصول.
- PR #36 دمج الـdeterministic three-stage production pipeline إلى `main-phase2@72edc44...`.
- الكود الحالي يتضمن `production_pipeline.py`، وتدقيق Domain Null/declustering، وعقود seismic، واختبارات الإنتاج. لذلك لا يُنقل `run_pipeline.py` أو تدقيق GEM القديم على هيئة كتلة من الفرع المتباعد.

### 2.3 فرع Markov

- تدقيق Rolling-MAD والسلوك وحقن التغيّر موجود في main بصيغ أحدث.
- بقيت إضافتان فريدتان في الفرع:
  - `extract_markov_rho_diagnostics`: فصل `rho_raw` عن `rho_clipped` وعن `rho_cusum_used` والتحقق من الاتساق والمدى.
  - `resolve_audit_source_commit`: ربط التقرير برأس الكود الذي جرى اختباره فعلياً.
- هاتان إضافتان observability/reporting، وليستا تغييراً في detector أو دليلاً على اعتماد Markov.
- القرار: لا دمج في MP0 ولا إدخالهما في P1. يمكن مراجعة نقلهما كتحسين لتقرير تدقيقي مستقل عند الحاجة.

### 2.4 PR #24

PR #24 مفتوح على قاعدة فرعية `p2.2.2-markov-calibration-audit` وليس على `main-phase2`. نطاقه تقرير Markov التاريخي، ولا يغير الكاشف. يبقى معزولاً؛ لا يوقف P0/P1/P2 ولا يدخل في هذا الدمج.

## 3. ما هو موجود فعلياً على main-phase2

| المكوّن | الحالة على `main-phase2` |
|---|---|
| D0 builder وworkflow | موجودان؛ الـworkflow ينشئ inventory/manifest/validation ويرفعها كـActions artifact |
| Source identity / lifecycle schemas | موجودة |
| Research Ledger kernel | موجود |
| WDI Trade DomainState | موجود، 29,004 سجل / 259 كيان / 5 مؤشرات / 2000–2024 |
| D1 registry | 21 مساراً؛ 15 موجوداً و6 مفقودة وفق آخر تقرير تكامل |
| P2 production pipeline | مدمج عبر PR #36؛ 519 مرشحاً (51 Pink Sheet و468 GEM/USGS) |
| Seismic null contract | موجود لكن حالته `design_contract_not_yet_validated` |
| Detector V1 | يبقى مجمداً ولا يدخل ضمن تعديل MP0 |

**تمييز تشغيل CI:** تشغيل PR #36 الذي تم فحصه أثبت نجاح `pr-gate` فقط؛ مراحل prepare/evaluate/aggregate والتدقيقات والنشر كانت skipped في حدث PR. لا أتعامل مع نجاح PR gate على أنه دليل بأن تشغيل الإنتاج الكامل نجح على `main-phase2@72edc44`. يلزم إثبات تشغيل push/dispatch الفعلي وقراءة jobs وartifacts قبل إعلان اكتمال التشغيل.

## 4. فجوات الأصول والنسخ التاريخية

آخر تقرير تكامل Engine 1 يسجل 6 مخرجات DomainState غير موجودة ضمن registry:
1. WGI annual institutional states.
2. WHO daily COVID states.
3. IMF IMTS shards: BRA / CAN / MEX / ZAF.

خمسة من هذه المسارات تقع تحت `experiments/**`؛ تبقى مراجع غير متاحة ولا يعاد إنشاؤها أو تعديلها داخل الأرشيف. ملف WGI أيضاً لا يُعتبر متحققاً بمجرد وجود summary يشير إلى estimates؛ يجب أن يوجد artifact فعلي وبصمة قابلة للتحقق.

بالنسبة إلى `available_at` و`source_revision`:
- سجلات WDI الحالية لا تحمل تاريخ إتاحة أو revision/vintage موثقاً؛ حالة point-in-time تبقى `UNKNOWN`.
- مرآة WEO لا تحتفظ بحقل IMF `Estimates Start After` أو ملاحظات country/series؛ حالة actual/estimate لصفوف النسخ المتأثرة تبقى `UNKNOWN`.
- أي لقطة قديمة لا تحفظ وقت الإتاحة تبقى خارج اعتماد `as-of` وإعادة بناء المعرفة المتاحة تاريخياً.
- لا نملأ الحقول بتاريخ جلب حديث، ولا نستنتج actual/estimate من شكل القيم، ولا نخلق rows بديلة للأصول الغائبة.

هذا القيد يمنع اعتماد استخدام تاريخي point-in-time لهذه البيانات؛ لكنه لا يمنع تحليلها الرجعي الموصوف بوضوح ولا يوقف الأفواج المستقلة في P2.

## 5. قرار الانتقال إلى P2 بحسب cohort

| cohort | ما يستمر الآن | ما يبقى ممنوعاً حتى تحقق إضافي |
|---|---|---|
| Pink Sheet | snapshot/hash integrity، كشف V1، null المناسب للتمثيل الشهري، قياس cohort-specific | وصف bootstrap conditional alarm probability بأنه FPR تشغيلي |
| GEM | snapshot/source identity، detector، null routing لكل سلسلة، قياسات المجموعة | استخدام بيانات أو صفوف غير مثبتة المصدر، أو دمج نتائج أفواج مختلفة في مقياس واحد |
| USGS | التحقق من الكتالوج والمجال والمقدار والتوقيت، detector diagnostics، اكتمال السجل، مقارنات null كاختبارات بحثية | قبول FPR/seismic null أو دلالة إنذار قبل completeness و`Mc(t,region)` وpoint-process validation |

**قانون التنفيذ:** فشل الأهلية لنموذج null في سلسلة لا يوقف تشغيل detector المرصود، ولا يوقف أفواجاً أخرى. لكنه يمنع إصدار إحصاء null أو اعتماد علمي لذلك النطاق. لا يُستخدم stationary bootstrap العام كـnull زلزالي.

إذن P2 يتقدم فعلياً على Pink Sheet وGEM وUSGS كمسارات مستقلة؛ أما إعلان إغلاق P2 علمياً فيظل مشروطاً بمقاييس الخطة: false alarms/decade أو ARL0، conditional detection delay، miss rate، FDR/alpha-spending، coverage/abstention/intervals، مع أحجام عينات وفصل الأفواج.

## 6. فجوة P1 التي لا تعتمد على الأصول المفقودة

عقد `source_record_observation_v1.schema.json` الحالي يعرّف `event_time` و`available_at` و`source_revision` و`revision_status`، لكنه لا يعرّف بعد:
- `observation_period_start`
- `observation_period_end`

وهما مطلوبان صراحة في P1 v2.1. يلزم إضافتهما مع اختبارات schema/identity وربطهما بدلالات التواتر؛ ولا يُستعاض عنهما بـ`event_time` عندما تكون نافذة الملاحظة مختلفة عن لحظة الحدث. هذه هي أول مهمة برمجية تالية في P1، ويمكن تنفيذها بالتوازي مع P2 cohort runs.

## 7. الحوكمة والصلاحيات — قراءة فقط

الـRuleset الحي رقم `27488330` لفرع `main-phase2`:
- enforcement: active.
- القواعد المقروءة: منع الحذف، منع non-fast-forward، required status checks، وتقييد update.
- required check الوحيد الظاهر في القراءة الحالية: `experiments-immutable`.
- `current_user_can_bypass = always`، وبعض bypass actors لديهم `always`.
- لا تظهر قاعدة PR أو مراجعة مستقلة في هذا الـRuleset.
- قائمة Rulesets الحالية التي أمكن قراءتها تحتوي Ruleset واحداً للفرع المذكور.
- Classic branch-protection state لا يُستنتج من القراءة السابقة التي أعادت 403.

وفق توجيه مالك المستودع، لم يُعدّل هذا العمل صلاحيات المستخدم أو GitHub App أو bypass أو شروط المراجعة أو Rulesets. لم تُغيّر حماية `experiments-immutable`، ولم تُلمس `experiments/**`.

## 8. تعديل MP0 في هذا الفرع

- تحديث D0 builder ليحلّ رؤوس الفروع الحالية وقت التنفيذ عند توفر remote refs، مع SHA fallback صريح إذا لم تكن الفروع fetched.
- تصحيح audited refs للفروع الثلاثة ورأس `main-phase2`.
- توسيع CORE_ARTIFACTS لتضمين production orchestrator وعقود وتدقيقات P2 الحالية.
- توثيق قرار cohort-scoped progression، وحالة `UNKNOWN` للنسخ والأصول الغائبة، دون تغيير detector أو البيانات المجمدة.
- إبقاء قرار D0 `P0_IN_PROGRESS`; نجاح بناء manifest لا يساوي إغلاق P0 أو اعتماد علمي.

## 9. ترتيب العمل التالي

1. مراجعة PR الخاص بـMP0 والتحقق من D0 artifacts وimmutable guard وobservation-foundation contracts على الرأس الدقيق.
2. تنفيذ تعديل P1 لإضافة `observation_period_start/end` واختبارات دلالات الفترة.
3. تشغيل production pipeline على `main-phase2` والتحقق من prepare/evaluate/aggregate/audits لجميع 519 مرشحاً، مع حفظ source/candidate hashes وعدم الخلط بين PR gate والتشغيل الكامل.
4. إغلاق كل cohort وفق بوابته ومقاييسه؛ تبقى القيود الزلزالية معلنة ولا تمنع مخرجات Pink Sheet/GEM.
5. استكمال P3/P4/P5/P6 وفق الخطة؛ لا يبدأ Engine 2 قبل اعتماد D6.

**حالة MP0 عند إعداد التقرير:** الفحص المباشر والتصنيف مكتملان؛ تعديل D0 والوثائق على فرع عمل منفصل بانتظار CI ومراجعة PR. لا يوجد ادعاء بدمج التغييرات أو إغلاق P0 قبل ظهور نتيجة GitHub.
