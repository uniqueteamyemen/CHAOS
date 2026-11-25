# امتداد Threshold 200

## الهدف
تنفيذ امتداد Threshold 200 المحدد في بروتوكول P1.4 المجمد عند `2ae721d`.

## النطاق والمنهجية
يُطبق Threshold 200 مرة واحدة فقط على كل عضو من C1 مصنف ضمن ADF_PASS_KPSS_FAIL إذا أثبت Artifact معايرة Threshold 90 الفعلي أنه NOT_CALIBRATABLE عند الموضع 0.30. تُشتق الهويات والكمية من Artifact المعايرة؛ لا عدد متوقع ولا قص للقائمة ولا IDs يدوية. يعاد استخدام development max-statistics نفسها دون إعادة توليد null أو تغيير AR order أو P0. لا Threshold 500.
لا يعرّف البروتوكول الأساسي امتداد Threshold 200 مستقلاً لـStratum 32؛ تحليل القدرة وحده لا ينشئ تفويضاً لاختبار threshold إضافي.

## المدخلات
Protocol v1.1.9 كما هو مجمد عند `2ae721d`، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
`threshold200_extension_results.json` مع عدد وهويات الحالات المشتقة من Artifact وSHA-256 وreplay command.

## معايير الحكم
GRID_LIMITED_CALIBRATED_AT_200 / STRUCTURAL_NOT_CALIBRATABLE_AT_200 / NOT_RUN

## التنفيذ
بعد اكتمال معايرة C1 فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.