# خريطة تكييف P2-C Evidence Pipeline على عقد P1.4

## PRESERVE
- `pilot_protocol.json` و`pilot_protocol.schema.json` كما هما عند `2ae721d`؛ لا تعاد كتابتهما لتطابق c5bda4d.
- `selected_cohort_frame`: 40 سلسلة (20 C1 + 20 C2) و19 حالة/سلسلة؛ إطار اختيار لا نتيجة تنفيذ.
- `cohort_manifest.json` وهويات C1/C2 وحصص 12/6/2 وبيانات C2.
- اختبار `test_focus_contract_has_unique_40_20_windows_and_minimum_length`.
- ملفا التدقيق `00-repository-integrity/README.md` و`01-unverified-claims-cleanup/README.md`.
- مرجع P2-B وA_FAST وA_CONSENSUS ومحرك P2-C والأرشيف `experiments/**`.

## ADAPT
- ترحيل runner وWorkflow الأدلة ووثائق `docs/p2c/evidence/` مع مطابقة البروتوكول والعينة المجمدين.
- إضافة seed phase `rearm` واختبارها؛ عدم تغيير تنفيذ `focus_reset_rearm` أو نافذة 20 observation.
- إزالة توقع 7 حالات فشل وأي سقف 15/285؛ اشتقاق العدد من Artifacts الفعلية.
- قصر Threshold 200 على النطاق المسجل: أعضاء C1 من Stratum 106 الذين يفشلون فعلياً عند Threshold 90 في الموضع 0.30. لا امتداد لـStratum 32 غير مسجل في baseline.
- جعل استيراد `arch` محصوراً في Track B، وتثبيت `arch==7.2.0` في preflight وبيئة postprocess.
- جعل Evidence workflow `workflow_dispatch` فقط، افتراضياً `contract_only`؛ تشغيل matrix لا يحدث إلا باختيار `full_20_series` صراحة.
- إضافة اختبار manifest-selection binding إلى contract-gates، وإجراء arch import وpy_compile وCLI check في preflight خفيف.

## فصل التنفيذ
1. Contract gates: capability، protocol، injection، cohort-selection binding.
2. Calibrate preflight: arch 7.2.0، import، py_compile، CLI.
3. Full execution: matrix معايرة C1 لا تبدأ إلا باختيار صريح بعد نجاح البوابات؛ postprocess مشروط بنجاحها.

## نطاق Pilot
- يعاير التشغيل المرشحين الـ20 المثبتين في C1.
- ينفذ Pilot على كل مرشح اجتاز فعلياً FOCuS calibration في المواضع الثلاثة وشرط `n>=150`.
- عدد السلاسل والحالات مشتق من Artifacts؛ لا استبدال IDs ولا سقف 15/285.
- C2 لا ينفذ ضمن مسار C1-only، وC3 يظل PENDING_EXTERNAL_EVIDENCE.

## UNVERIFIED / NOT_RUN
Threshold 90، Threshold 200، Track B، Rearm overlap وPilot تظل NOT_RUN حتى تنتج Artifacts أصلية. لا تشغيل ثقيل أثناء الترحيل أو اجتياز العقود.

## الدمج
نجاح CI وحده لا يمنح اعتماداً؛ الجودة وholdout وP0 والاتجاه والتأخير وrecall والتغطية بوابات مستقلة.