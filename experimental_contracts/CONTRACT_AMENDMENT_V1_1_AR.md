# تصحيح Experimental Contract إلى v1.1

## سبب التصحيح

فشل أول تشغيل لـTFT قبل الوصول إلى التدريب لأن مصفوفة `COMPLETE_140` لم تكن رقمية بالكامل كما أوحى الفحص الأول. ظهرت ست خلايا EIA بقيمة marker نصية `--` للكيان `SRB` في السنوات 2000–2005. لم تكن هذه القيم صفراً، ولم تكن قيماً مفقودة ممثلة بـNaN؛ لذلك كان تمريرها إلى النموذج غير مسموح.

## الإجراء المتخذ

لم تُعدّل أي قيمة في raw layer، ولم تُستبدل `--` بصفر أو متوسط، ولم تُجرَ تعبئة أو interpolation. أُعيد فحص الـ194 كياناً باستخدام numeric coercion فقط، واستُبعد كل كيان يحتوي marker أو قيمة غير رقمية في أي من الأعمدة الإحدى عشرة خلال 2000–2024.

نتجت نسخة مشتقة جديدة من **139 كياناً** و3,475 صفاً و38,225 خلية، وجميع خلاياها رقمية وموجودة. تبقى نسخة الـ194، ونسخة الـ140 القديمة، وسجل markers محفوظة للمراجعة ولا تُحذف.

## الإعداد المصحح

| البند | v1 | v1.1 المصحح |
|---|---:|---:|
| الكيانات | 140 | 139 |
| الصفوف | 3,500 | 3,475 |
| train windows | 1,400 | 1,390 |
| validation windows | 560 | 556 |
| test windows | 700 | 695 |
| إجمالي windows | 2,660 | 2,641 |
| missing/marker داخل نسخة التدريب | فشل مخفي سابقاً | صفر بعد الاستبعاد الصريح |

## الحالة العلمية

هذا ليس تنظيفاً قسرياً ولا تحايلاً لرفع الأداء. إنه تصحيح لخطأ في تعريف الاكتمال: الفحص الأول عدّ النص `--` كخلية غير فارغة. قاعدة v1.1 أكثر تحفظاً وتحافظ على عدم imputation. يجب استخدام v1.1 في baseline وTFT، مع إبقاء فشل v1 مسجلاً كـ`PRE_TRAIN_FAILURE`.

## الملفات

- المصفوفة المشتقة: `catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv`
- ملخص المصفوفة: `catalog_first/readiness_gate/macro_plus_eia_energy/NUMERIC_COMPLETE_MATRIX_V1_1_SUMMARY.json`
- سجل markers: `experiments/macro_plus_eia_energy/NON_NUMERIC_MARKER_AUDIT.json`
- profile الاكتمال: `experiments/macro_plus_eia_energy/NUMERIC_COMPLETENESS_PROFILE.json`
- العقد المصحح: `experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1_1.json`

بعد تثبيت v1.1، يجب إعادة بناء window audit وreproducibility lock وbaseline suite ثم إعادة TFT. لا تُستخدم نتائج التشغيل الفاشل في التقييم.
