# Pilot Scope — C1 Artifact-Eligible Subset

## الهدف
تنفيذ Pilot جزئي على C1 فقط بعد اجتياز معايرة كل سلسلة لشروط الأهلية المجمدة.

## إطار الاختيار مقابل نطاق التنفيذ
يحفظ البروتوكول `selected_cohort_frame` إطار اختيار من 40 سلسلة: 20 من C1 و20 من C2، مع 19 حالة لكل سلسلة (حالة أصلية و18 حقناً). قيمة 40/760 تصف إطار الاختيار فقط؛ ليست تشغيل Pilot منفذاً ولا سقفاً تنفيذياً.
يعالج Evidence Pipeline مرشحي C1 العشرين المثبتين في `cohort_manifest.json`. بعد اكتمال المعايرة، ينفذ Pilot على جميع سلاسل C1 التي اجتازت فعلياً شروط FOCuS في المواضع الثلاثة وشرط `n>=150`. يحسب عدد السلاسل والحالات من Artifact الأهلية وبروتوكول التشغيل. لا حد مسبق 15 سلسلة/285 حالة، ولا استبدال لهويات غير المؤهلة. C2 لا ينفذ في هذا المسار، وC3 خارج النطاق.

## المدخلات
Protocol v1.1.9 كما هو مجمد عند `2ae721d`، manifest، selection artifact، ملفات معايرة C1 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
`pilot_run_manifest.json` و`pilot_results.json` مع السلاسل المؤهلة الفعلية وعدد الحالات الفعلي وSHA-256 وreplay command.

## معايير الحكم
COMPLETE / PILOT_PARTIAL / NOT_RUN / INCONCLUSIVE

## التنفيذ
بعد نجاح contract-gates وcalibrate-preflight واكتمال معايرة مرشحي C1. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.