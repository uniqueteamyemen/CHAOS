# 24 ساعة

## الهدف
24 ساعة ضمن إغلاق P2-C.

## النطاق والمنهجية
الحد الكلي 24 ساعة؛ GitHub-hosted job قد يفرض سقفاً أقصر، وعندها تُحفظ الحالة الجزئية قبل الإنهاء.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
execution_summary.json وpilot_run_manifest.json مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
COMPLETE / PILOT_PARTIAL

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
