# خريطة إصلاح P2-C

## PRESERVE
- cohort_manifest.json وهويات Cohorts وحصص 12/6/2 وبيانات C2.
- مرجع P2-B وخطي A_FAST وA_CONSENSUS.
- محرك P2-C وvendor وBreakDetectorV1.
- experiments/** وكل الأرشيف التاريخي.

## REPAIR
- protocol/schema v1.1.9، مع إلغاء أي نتائج غير موثقة وإظهار NOT_RUN.
- capability envelope: إزالة التكرار.
- injection_runner: rearm seed stream وشرح 20 observation.
- tests: لا assertions على أرقام يدوية؛ اختبار حالة NOT_RUN.
- STATUS والتوثيق: نقطة دخول موحدة وREADME لكل نقطة.
- Workflow واحد لفرع التنفيذ.

## UNVERIFIED / NOT_RUN
Threshold 90، Threshold 200، Track B، Rearm overlap، Pilot.

## Pilot
40 سلسلة تبقى candidate universe. التشغيل <=15 C1 مؤهلة ×19=285؛ الاختيار بعد Artifact معايرة فعلي. لا تبديل IDs.

## الدمج
نجاح CI وحده لا يمنح اعتماداً. الجودة، holdout، P0، الاتجاه، التأخير، recall والتغطية بوابات مستقلة.
