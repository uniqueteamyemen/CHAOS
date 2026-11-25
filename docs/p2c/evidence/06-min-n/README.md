# min_n=150

## الهدف
min_n=150 ضمن إغلاق P2-C.

## النطاق والمنهجية
FOCuS adapter يرفض n<150 بـNOT_ELIGIBLE وFOCUS_MIN_N_150_REQUIRED؛ لا يحتسب miss ولا recall.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
integrity_report.json وpilot_results.json مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
PASS / NOT_ELIGIBLE

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
