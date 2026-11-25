# تدقيق سلامة P2-C / P1.4 — Evidence-First

نقطة الالتقاط: feat/p1-4-capability-envelope-pilot-v1-20261125@f6a69cfde01482adf3045e8b54886dbe8f68eb52. هذا تصنيف حالة وليس نتيجة تجربة.

| الملف/النطاق | الحالة | القرار |
|---|---|---|
| cohort_manifest.json | PRESERVE | تثبيت هويات C1/C2 وSHA؛ لا استبدال. |
| pilot_protocol.json | REPAIR | v1.1.9، إلغاء النتائج غير الأصلية، Pilot 15/285 كحد أعلى. |
| pilot_protocol.schema.json | REPAIR | مواءمة v1.1.9. |
| capability_envelope.json | REPAIR | إزالة input_contract المكرر. |
| injection_runner.py | REPAIR | إضافة seed phase rearm وتصحيح تعليق 15 إلى 20. |
| اختبارات P1.4 | REPAIR | إزالة assertions الخاصة بنتائج overlap غير المنفذة وإثبات NOT_RUN. |
| STATUS.md | REPAIR | إضافة حالة التنفيذ دون تعديل P2-B. |
| experiments/** | PRESERVE | أرشيف ثابت. |
| structural_engine/isolated_break_detector_v1/** | PRESERVE | لا تعديل على الكاشف أو خطوط A_FAST/A_CONSENSUS. |
| النتائج اليدوية المحذوفة | REVERTED/UNTRUSTED | لا يعاد استخدامها. |
| Q1/Q2/Q3 | NOT_RUN | لا Artifact أصلي يثبت Threshold 200 أو معايرة 90 أو قياس 1000 rearm. |

## Cohorts المثبتة
- C1: 147 G1 composite-fail؛ 106 ADF-pass/KPSS-fail، 32 both-fail، 9 ADF-fail/KPSS-pass.
- C1 Pilot: 20، حصص 12/6/2.
- C2: 50 (43 GEM/7 Pink)، Pilot subset 20 (17 GEM/3 Pink).
- C3: PENDING_EXTERNAL_EVIDENCE.
- اختيار Cohorts لا يثبت معايرة Detector.

Threshold 200 سيطبق على الحالات الفعلية غير المعايرة بعد Threshold 90؛ إذا اختلف العدد عن المتوقع 7 لا تُقص القائمة. لا توجد قياسات overlap حتى تنتجها Actions. كل نتيجة رقمية تتطلب run ID وcommit SHA وArtifact SHA-256 وreplay command.
