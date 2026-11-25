# Reproducibility

## الهدف
Reproducibility ضمن إغلاق P2-C.

## النطاق والمنهجية
بصمات المصدر والبروتوكول والبذور والمعلمات وcommit وrun_id/replay لكل artifact؛ لا raw observations في outputs.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
pilot_run_manifest.json وSHA256SUMS.txt مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
COMPLETE / PARTIAL

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
