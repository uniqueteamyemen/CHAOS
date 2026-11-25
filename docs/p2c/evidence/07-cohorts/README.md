# C1/C2

## الهدف
C1/C2 ضمن إغلاق P2-C.

## النطاق والمنهجية
مطابقة IDs من manifest وselection artifact وG1 shards الأربعة؛ حفظ 12/6/2 و43/7 و17/3، ومنع تعميم C2/C3.

## المدخلات
Protocol v1.1.9، manifest، selection artifact، بيانات P2.2 وبصماتها، وrun_id/commit SHA من GitHub Actions.

## المخرجات
integrity_report.json مع SHA-256 وreplay command داخل artifact metadata.

## معايير الحكم
PASS / FAIL

## التنفيذ
Workflow CHAOS P1.4 Evidence-First P2-C Pipeline فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.
