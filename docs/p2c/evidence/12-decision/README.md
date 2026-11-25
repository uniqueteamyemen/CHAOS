# قرار P2-C

## الهدف
قرار P2-C ضمن إغلاق P2-C.

## النطاق والمنهجية
Pilot C1-only لا يثبت C2/C3. النتيجة الجزئية PARTIAL_VALIDATION؛ LOCKED_REJECTED فقط بعد استيفاء شروط الرفض لكل cohort مطلوب.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
p2_c_decision_report.json مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
PARTIAL_VALIDATION / LOCKED_REJECTED / INCONCLUSIVE

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
