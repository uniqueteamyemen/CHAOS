# Rearm

## الهدف
Rearm ضمن إغلاق P2-C.

## النطاق والمنهجية
1000 null traces لكل سلسلة مؤهلة، 40 initial quiet و20 post-hit؛ قياس overlap actual عند مواضع 0.30/0.50/0.70.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
rearm_overlap_results.json مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
ESTIMABLE / INCONCLUSIVE / NOT_ELIGIBLE

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
