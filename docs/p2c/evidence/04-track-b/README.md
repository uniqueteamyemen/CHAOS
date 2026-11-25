# Track B

## الهدف
Track B ضمن إغلاق P2-C.

## النطاق والمنهجية
AR(1)/AR(p)، GARCH(1,1)، ARCH-LM، lag-12، trend، FOCuS alerts على الأصل وتوزيع null؛ بلا حقن وبلا تغيير معلمات.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
track_b_diagnostics.json مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
COMPLETE / NOT_ESTIMABLE / NOT_RUN

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
