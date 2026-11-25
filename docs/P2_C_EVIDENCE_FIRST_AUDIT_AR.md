# تدقيق سلامة P1.4 — المسار الهندسي التشغيلي

نقطة الارتكاز: `feat/p1-4-capability-envelope-pilot-v1-20261125@2ae721d`. جميع العقود المجمدة تظل مرجعاً غير قابل للتعديل في هذا التكييف.

| النطاق | الحالة | القرار |
|---|---|---|
| `pilot_protocol.json` وSchema | PRESERVE | مطابقان حرفياً لـ2ae721d، بما فيه selected_cohort_frame وبيانات Stratum 32. |
| `cohort_manifest.json` | PRESERVE | هويات C1/C2 وحصص الاختيار دون استبدال. |
| Capability envelope واختبار 40/20 | PRESERVE | لا تعديل على العقد أو اختبار النوافذ. |
| اختبار cohort-selection binding | PRESERVE | جزء من بوابات العقود. |
| ملفا التدقيق 00 و01 | PRESERVE | محفوظان دون تعديل. |
| Injection runner | ADAPT | دعم seed phase باسم rearm مع الحفاظ على 40 الأولية و20 بعد كل hit. |
| Threshold-90 calibration | ACTIVE | المصدر الوحيد لتثبيت عتبات Pilot. |
| Rearm validation | ACTIVE | فحص مستقل لسلوك إعادة التسليح على المسارات الفارغة. |
| C1 detector-comparator Pilot | ACTIVE | يضم جميع مرشحي C1 الذين يجتازون بوابات المعايرة الفعلية. |
| Threshold-200 extension | NOT EXECUTED ENGINE SCOPE | يبقى مسجلاً في البروتوكول التاريخي، ولا يستخدم لتغيير أهلية العينة التشغيلية. |
| Track B / GARCH / ARCH-LM / lag-12 / trend | REMOVED | خارج مسار المحرك ولا يشارك في المعايرة أو المقارنة. |
| Workflow triggers | MANUAL ONLY | لا push triggers؛ contract_only هو الوضع الافتراضي. |

## إطار الاختيار
- C1: 20 مرشحاً مختاراً وفق حصص البروتوكول.
- C2: 20 مرشحاً في إطار الاختيار فقط، غير منفذ في هذا المسار.
- selected_cohort_frame: 40 سلسلة و760 حالة إطار اختيار، وليس نتيجة تنفيذ.
- Stratum 32: `n_series=6` في تحليل القدرة، و`series_count=null` في سجل امتداد Threshold 200؛ الحقلان يصفان قياسين مختلفين.

## حدود الادعاء
لا توجد نتائج معايرة أو Pilot فعلية حتى تنتجها GitHub Actions. أي نتيجة لاحقة يجب أن تحتوي source commit وrun ID وSHA-256 وreplay command. نجاح العقود لا يعني نجاح المحرك في كشف الانقطاعات ولا يمنح اعتماد إنتاج.
