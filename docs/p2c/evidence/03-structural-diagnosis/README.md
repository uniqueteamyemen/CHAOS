# التشخيص البنيوي

## الهدف
التشخيص البنيوي ضمن إغلاق P2-C.

## النطاق والمنهجية
تشخيص حالات عدم المعايرة بعد 200 من AR والابتكارات وnull max-statistics؛ لا تغيير AR order أو null model أو P0 أو cohort.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
track_b_diagnostics.json مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
ESTIMATED / NOT_ESTIMABLE / NOT_RUN

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
