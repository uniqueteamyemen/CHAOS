# Integrity

## الهدف
حماية العقد وبصمات المدخلات ومصدر التنفيذ.

## النطاق والمنهجية
Evidence workflow يدوي فقط عبر workflow_dispatch؛ لا يحتوي push trigger. يبدأ افتراضياً بوضع contract_only، ويجري contract gates وفحص بيئة arch/CLI فقط. لا تُطلق مصفوفة معايرة C1 إلا باختيار full_20_series صراحة وبعد نجاح البوابات. Workflow بوابة capability الخفيفة منفصل، ومقيد بالفرع النشط.

## المدخلات
Protocol v1.1.9 المجمد عند 2ae721d، manifest، selection artifact وG1 shards الأربعة، وrun_id/commit SHA من GitHub Actions.

## المخرجات
execution_provenance.txt وSHA256SUMS.txt مع SHA-256 وreplay command.

## معايير الحكم
PASS / FAIL

## التنفيذ
كل التحقق والحساب في GitHub Actions فقط. لا تشغيل محلي ولا نتائج مكتوبة يدوياً.