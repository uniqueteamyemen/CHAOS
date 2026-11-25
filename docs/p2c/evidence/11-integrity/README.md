# Integrity

## الهدف
Integrity ضمن إغلاق P2-C.

## النطاق والمنهجية
Workflow لفرع التنفيذ فقط، لا push trigger على main-phase2 أو الفروع الأخرى؛ كل الاختبارات والحسابات في Actions.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
execution_provenance.txt وSHA256SUMS.txt مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
PASS / FAIL

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
