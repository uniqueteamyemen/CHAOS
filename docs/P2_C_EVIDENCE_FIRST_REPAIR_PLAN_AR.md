# خطة الإغلاق الهندسي لـP1.4

## PRESERVE
- `pilot_protocol.json` و`pilot_protocol.schema.json` حرفياً عند `2ae721d`.
- `cohort_manifest.json` وهويات C1/C2 وحصص الاختيار.
- `capability_envelope.json` واختبار `test_focus_contract_has_unique_40_20_windows_and_minimum_length`.
- اختبار cohort-selection manifest binding.
- ملفا التدقيق `00-repository-integrity/README.md` و`01-unverified-claims-cleanup/README.md` دون تعديل.
- A_FAST وA_CONSENSUS كخطّي مقارنة للقراءة فقط.

## ACTIVE ENGINE PATH
1. Threshold-90 calibration للمرشحين العشرين المثبتين في C1، باستخدام بيانات التطوير لاختيار العتبات وholdout للتقييم.
2. Rearm validation مع 40 observation أولية و20 observation بعد كل hit.
3. Detector-comparator Pilot على كل مرشح اجتاز فعلياً معايرة Threshold-90 في المواقع الثلاثة وشرط `n>=150`.
4. حفظ provenance وrun ID وcommit SHA وArtifact SHA-256 وreplay command.

## OUT OF OPERATIONAL SCOPE
- Threshold-200: يظل مدوناً في البروتوكول المجمد، لكنه لا يستخدم كـfallback لتغيير أهلية المرشحين في Pilot الهندسي.
- Track B: حذف من runner وworkflow؛ لا GARCH أو ARCH-LM أو lag-12 أو trend diagnostics في هذا المسار.
- C2 وC3: خارج تنفيذ C1 Pilot الحالي.

## WORKFLOW SAFETY
- Evidence workflow يدوي فقط عبر `workflow_dispatch`.
- الوضع الافتراضي `contract_only`: عقود + فحص بيئة + CLI.
- مصفوفة C1 لا تبدأ إلا باختيار `full_20_series` صراحة بعد نجاح البوابات.
- Postprocess يعمل فقط في وضع التشغيل الكامل وبعد نجاح contract-gates وruntime preflight؛ ويسمح بتقرير PARTIAL إذا أخفق بعض أفراد المصفوفة.

## ACCEPTANCE
نجاح contract gates وruntime preflight يثبت سلامة الترحيل والبيئة، ولا يثبت قدرة كشف إنتاجية. اعتماد المحرك يتطلب مراجعة نتائج Pilot الفعلية، بما فيها recall، false alerts، اتجاه الإشارة، التأخير والتغطية.
