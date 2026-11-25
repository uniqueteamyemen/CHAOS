# تدقيق سلامة P2-C / P1.4 — Evidence-First

نقطة الالتقاط: `feat/p1-4-capability-envelope-pilot-v1-20261125@2ae721daa683e917af3495b59bb77fc25ad8b0d8`. هذا تصنيف حالة وليس نتيجة تجربة.

| الملف/النطاق | الحالة | القرار |
|---|---|---|
| `cohort_manifest.json` | PRESERVE | تثبيت هويات C1/C2 وSHA؛ لا استبدال ولا إعادة أخذ عينة. |
| `pilot_protocol.json` | PRESERVE | الإبقاء حرفياً على v1.1.9 عند 2ae721d، بما فيه `selected_cohort_frame` ونطاق الاختيار 40/760. |
| `pilot_protocol.schema.json` | PRESERVE | لا تعديل على schema المجمد. |
| `capability_envelope.json` | PRESERVE | إبقاء عقد القدرة كما هو؛ لا حذف لحقول أو اختبارات قائمة. |
| `injection_runner.py` | ADAPT | إضافة `rearm` إلى مراحل البذور فقط؛ الحفاظ على نافذة 40 الأولية و20 بعد كل hit. |
| اختبارات P1.4 | PRESERVE + ADD | إبقاء اختبار 40/20 وإضافة اختبار seed لـrearm وربط اختبار manifest-selection ببوابات العقد. |
| ملفات تدقيق P1.4 | PRESERVE | إبقاء README لسلامة المستودع وتنظيف الادعاءات غير المتحققة دون حذف. |
| Evidence Pipeline | PORT + ADAPT | نقل runner والوثائق والـworkflow مع مطابقة البروتوكول والعينة؛ لا نسخ أعمى من c5bda4d. |
| Workflow | GATED | Evidence workflow يدوي فقط؛ contract_only افتراضي، وتشغيل C1 يتطلب اختياراً صريحاً منفصلاً. |
| النتائج اليدوية غير المسندة | UNTRUSTED | لا يعاد استخدامها أو تحويلها إلى نتائج تشغيل. |

## Cohorts المثبتة
- C1: 147 سجلاً في المجموعة الأم؛ إطار Pilot يحتوي 20 سلسلة مختارة بحصص 12/6/2.
- C2: 50 سجلاً (43 GEM/7 Pink Sheet)؛ إطار Pilot يحتوي 20 سلسلة (17 GEM/3 Pink).
- `selected_cohort_frame`: 40 سلسلة (20 C1 + 20 C2) و760 حالة اختيار؛ إطار اختيار غير منفذ، وليس حجم Pilot فعلياً.
- C3: PENDING_EXTERNAL_EVIDENCE.

## امتداد Threshold 200
البروتوكول الأساسي يجيز الاختبار مرة واحدة لكل عضو C1 من Stratum 106 (ADF_PASS_KPSS_FAIL) يثبت Artifact Threshold 90 الفعلي عدم قابليته للمعايرة عند الموضع 0.30. العدد والهويات غير مثبتة مسبقاً، وتُشتق من Artifact دون قصّ. تحليل القدرة لـStratum 32 لا ينشئ وحده امتداد Threshold 200 إضافياً؛ لا تُستخدم IDs من نسخة c5bda4d.

لا توجد نتائج معايرة أو overlap أو Pilot أصلية حتى تنتجها Actions. كل نتيجة رقمية تتطلب run ID وcommit SHA وArtifact SHA-256 وreplay command.