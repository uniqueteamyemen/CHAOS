# Pilot 15/285

## الهدف
Pilot 15/285 ضمن إغلاق P2-C.

## النطاق والمنهجية
حتى 15 C1 مؤهلة ×19 حالة؛ إن قل العدد الفعلي فلا استبدال أو تبديل IDs.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
pilot_run_manifest.json مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
PILOT_PARTIAL / NOT_RUN

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
