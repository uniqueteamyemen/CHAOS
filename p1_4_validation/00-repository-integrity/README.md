# المرحلة الأولى — تقرير سلامة مستودع CHAOS / P1.4

**الفرع:** `feat/p1-4-capability-envelope-pilot-v1-20261125`  
**Commit الحالة التي يغطيها التدقيق:** `f6a69cfde01482adf3045e8b54886dbe8f68eb52`  
**تاريخ اللقطة:** 2026-11-25  
**الحكم العام:** `NOT_CLEAN` — التقرير يحدد الإصلاحات المطلوبة؛ لم يتم تنظيف المستودع أو إغلاقها بعد.

## 1. خلاصة تنفيذية

لم يكن الفرع عند Commit الحالة نظيفاً أو جاهزاً للتجارب العلمية. البروتوكول والاختبارات والعقد التشغيلي لم تكن متسقة بالكامل، كما لم يكن مسار تنفيذ P1.4 العلمي موجوداً كـWorkflow متكامل. لا توجد أدلة تشغيل أصلية لمعايرة Threshold 90 أو Threshold 200 أو قياس Rearm أو Pilot.

الملفات الرقمية التي حُذفت سابقاً لإبطال النتائج غير المدعومة غير موجودة في الفرع عند لقطة التدقيق:
- `p1_4_validation/calibration_results_all_strata.json`
- `p1_4_validation/track_b_diagnostics.json`

كذلك لا توجد:
- `p1_4_validation/pilot_run_manifest.json`
- `scripts/p1_4/execute_p1_4.py`
- `scripts/p1_4/run_pilot.py`
- Workflow مخصص لتنفيذ مراحل المعايرة وقياسات Rearm وTrack B والـPilot.

غياب هذه الملفات يعني أن النتائج المقابلة `NOT_RUN`، وليس أنها فشلت أو نجحت.

## 2. تصنيف الملفات

| الملف / المكوّن | التصنيف | نتيجة التدقيق / الإجراء المطلوب |
|---|---|---|
| `p1_4_validation/cohort_manifest.json` | `PRESERVE` | حفظ هويات Cohorts وبيانات الاختيار المثبتة. نطاق 40 سلسلة/760 حالة هو إطار اختيار C1/C2، ولا يُعامل كتنفيذ Pilot. |
| `scripts/p1_4/build_cohort_selection.py` | `PRESERVE` | إبقاء منطق اختيار C1 وC2 والتحقق من الهويات والحصص. لا نعيد اختيار العينات لتغطية نتائج غير مؤهلة. |
| `p1_4_validation/pilot_protocol.json` | `REPAIR` | البروتوكول عند 1.1.8 احتوى بقايا متعارضة: بيانات تداخل صفرية مثبتة يدوياً، إحالات إلى 11 سلسلة معايرة، ومقاطع Scope قديمة. يجب أن تكون هذه القياسات `NOT_RUN` وأن يفصل الإطار الأصلي عن Pilot الجزئي. |
| `p1_4_validation/pilot_protocol.schema.json` | `REPAIR` | مواءمة إصدار Schema مع البروتوكول وإزالة أي تعارض بين الحقول المطلوبة وحالة التنفيذ. |
| `p1_4_validation/capability_envelope.json` | `REPAIR` | تكرار عنصر `40_initial_calibration_observations` في عقد FOCuS؛ يجب إزالة التكرار مع إبقاء بوابات الأهلية. |
| `p1_4_validation/injection_runner.py` | `PRESERVE + REPAIR` | منطق 40 مشاهدة أولية و20 مشاهدة Rearm وحد FOCuS عند 150 موجود. تعليق داخل الدالة كان يشير إلى 15 بدلاً من 20؛ يصحح التعليق دون تغيير السلوك المجمد. |
| `tests/governance/test_p1_4_pilot_protocol.py` | `REPAIR` | احتوى Assertions لنتائج تداخل تساوي صفراً ولنطاق Track A قديم 16/304. لا يجوز أن تختبر القيم التجريبية غير المنفذة كحقائق. |
| `tests/governance/test_p1_4_capability_envelope.py` | `PRESERVE` | الإبقاء على اختبارات fail-closed وmin_n=150 والعقود؛ تشغيلها داخل GitHub Actions فقط. |
| `tests/governance/test_p1_4_injection_runner.py` | `PRESERVE` | الإبقاء على اختبارات Adapter والعقود 40/20 وINVALID_INJECTION. نجاح هذه الاختبارات لا يثبت المعايرة الإحصائية. |
| `STATUS.md` | `REPAIR` | الحالة القديمة تتضمن آلية تشغيل `[skip-p2-full]` لم تعد كافية كضمان. يجب أن يطابق سجل الحالة مراحل التنفيذ وقيود التشغيل اليدوي. |
| `.github/workflows/p1-4-capability-gates.yml` | `REPAIR` | إعدادات التشغيل التلقائي Push/PR تتعارض مع قاعدة التشغيل الصريح؛ يلزم تحويلها إلى تشغيل يدوي فقط. |
| `.github/workflows/p1-4-cohort-selection.yml` | `REPAIR` | يحتوي Push trigger؛ يلزم تشغيل يدوي فقط لمنع تشغيل غير مقصود عند تحديث ملفات الاختيار. |
| `scripts/p1_4/execute_p1_4.py` | `MISSING / BUILD` | لا يوجد محرك تنفيذ لمعايرة 90/200 أو Rearm أو Track B. |
| `scripts/p1_4/run_pilot.py` | `MISSING / BUILD` | لا يوجد Entry point لتشغيل Pilot من Artifact eligibility. |
| `.github/workflows/p1-4-evidence-pipeline.yml` | `MISSING / BUILD` | لا يوجد Workflow موحد ومقسم إلى مراحل يرفع النتائج الأصلية وبصماتها. |
| `p1_4_validation/pilot_run_manifest.json` | `NOT_RUN / MISSING` | لا ينشأ إلا من تشغيل Pilot حقيقي؛ ممنوع إنشاؤه يدوياً. |
| ملفات المعايرة وTrack B ونتائج Rearm | `NOT_RUN / ABSENT` | لا تُنشأ ملفات نتائج ثابتة إلا من Artifacts ينتجها GitHub Actions. |

## 3. الأدلة التشغيلية التي يمكن اعتمادها

1. **Cohort selection:** Workflow Run `45557117680` اكتمل بنجاح وأنتج Artifact ID `14995009654`. هذا يثبت عملية اختيار/مطابقة Cohorts فقط؛ لا يثبت معايرة Threshold 90 أو 200، ولا Rearm ولا Recall.
2. **Cohort selection السابق:** Run `45555067080` اكتمل وأنتج Artifact ID `14994992764`، وهو أيضاً دليل اختيار Cohorts فقط.
3. **Threshold 90 على 20 سلسلة:** `NOT_RUN` — لا يوجد Run ID وArtifact SHA أصلي.
4. **Threshold 200 على سبع سلاسل من Stratum-106:** `NOT_RUN` — لا يوجد Run ID وArtifact SHA أصلي.
5. **قياس 20-window overlap باستخدام 1000 Null traces لكل سلسلة:** `NOT_RUN` — لا يوجد Run ID وArtifact SHA أصلي.
6. **Track B وPilot:** `NOT_RUN` — لا يوجد Artifact أصلي أو replay command.

نجاح عقد أو اختبار Cohort لا يُحوّل إلى دليل أداء كاشف أو معايرة علمية.

## 4. سلامة الفرع والتغييرات

- رأس الفرع عند التدقيق: `f6a69cfde01482adf3045e8b54886dbe8f68eb52`.
- هذا التقرير لا يوصي بإعادة كتابة تاريخ Git ولا بحذف commits بصورة جماعية.
- لا يوجد في هذه المرحلة `REVERT` منفذ؛ لا يمكن اختيار نقطة رجوع آمنة اعتماداً على اسم Commit وحده.
- يجب الحفاظ على بيانات Cohort المثبتة وفصلها عن نتائج التجارب غير الموجودة.
- التصنيف `REPAIR` يعني إصلاحاً في Commit قابل للتدقيق، وليس إذناً بإخفاء تاريخ التعديلات السابقة.

## 5. بوابات ما قبل التجارب

1. توحيد البروتوكول وSchema وإزالة كل Assertion يستند إلى أرقام غير منفذة.
2. إصلاح عقد Capability Envelope وتعليق 20-point Rearm.
3. فصل إطار اختيار 40/760 عن Pilot C1 الجزئي بحد أقصى 15/285؛ العدد الفعلي يتحدد من Artifacts أهلية المعايرة، وقد يقل عن 15.
4. إضافة Entry points وWorkflow صريح لكل مرحلة.
5. جعل Workflows الخاصة بـP1.4 يدوية فقط.
6. إضافة README مستقل لكل نقطة من النقاط الاثنتي عشرة.
7. تشغيل عقد واختبارات النزاهة عبر GitHub Actions، ثم بدء Threshold 90.

## 6. حدود هذا التقرير

هذا تقرير لقطة الحالة على Commit المذكور. لا يدّعي أن المستودع نُظّف، أو أن الإصلاحات طُبقت، أو أن أي تجربة علمية اكتملت. التصنيف `UNVERIFIED` ينطبق على أي نتيجة لا تسندها سجلات تشغيل وArtifacts أصلية. يجب عدم استعمال أي رقم من ملفات النتائج المحذوفة أو الادعاءات التي أُبطلت سابقاً.
