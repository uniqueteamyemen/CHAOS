# معايرة Threshold 90

## الهدف
معايرة Threshold 90 ضمن إغلاق P2-C.

## النطاق والمنهجية
1000 Development و1000 Holdout لكل سلسلة C1 ولكل موضع 0.30/0.50/0.70. اختيار أقل threshold من الشبكة المجمدة التي تجعل حد Wilson الأعلى أحادي الطرف لـP0 <=0.10. لا إعادة معايرة على Holdout.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
calibration_results_all_strata.json مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
CALIBRATED / NOT_CALIBRATABLE / INCONCLUSIVE / NOT_ELIGIBLE

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
