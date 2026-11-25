# امتداد Threshold 200

## الهدف
امتداد Threshold 200 ضمن إغلاق P2-C.

## النطاق والمنهجية
يُطبق 200 مرة واحدة على كل سلسلة Stratum 106 فشلت فعلياً عند 90 في موضع 0.30؛ العدد المتوقع 7 reconciliation لا quota. امتداد DJI/ECU/HKG مشروط بفشلها الفعلي في 90. لا Threshold 500.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
threshold200_extension_results.json مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
GRID_LIMITED_CALIBRATED_AT_200 / STRUCTURAL_NOT_CALIBRATABLE_AT_200 / NOT_RUN

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
