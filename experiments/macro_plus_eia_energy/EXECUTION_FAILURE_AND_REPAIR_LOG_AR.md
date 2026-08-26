# سجل الفشل والإصلاح — TFT baseline v1.1

## الحالة

تم تدريب TFT بنجاح على النسخة المصححة v1.1، لكن الحملة مرت بإخفاقات تنفيذية موثقة أدت إلى إصلاحات في الطبقة المشتقة/الأدوات فقط. لم تُعدّل raw data، ولم تُستخدم أي قيمة تقديرية.

| المرحلة | الفشل | السبب | الإصلاح | أثر raw/العقد |
|---|---|---|---|---|
| Dataset construction | أسماء WDI ذات النقاط رفضها `TimeSeriesDataSet` | API يمنع `.` في أسماء الأعمدة | إنشاء aliases مشتقة آمنة وحفظ `feature_name_map` | raw لم يتغير |
| Normalizer | `TorchNormalizer` فشل عند fit على DataFrame | استخدامه في `scalers` لم يكن متوافقاً مع المسار الداخلي للإصدار | استخدام `target_normalizer=None` و`scalers={feature: None}` لمنع auto-scaling | لا scaling ولا تعديل raw |
| Dataset assertion | target موجود داخل `scalers` | API يفصل target normalizer عن scalers | استبعاد target من قاموس scalers | العقد محفوظ |
| Numeric integrity | فشل التحويل بسبب `--` في EIA لسلسلة SRB 2000–2005 | الفحص الأول عدّ marker النصي كخلية غير فارغة | إعادة فحص 194 كياناً واستبعاد كل كيان غير رقمي؛ الناتج 139 كياناً | لا استبدال ولا imputation |
| Contract correction | v1 كان يعلن 140 كياناً دون اكتشاف marker | تعريف الاكتمال السابق لم يطبق numeric coercion | إنشاء v1.1 وتسجيل سبب الاستبعاد والملفات السابقة | v1 محفوظ كسجل تاريخي |
| TFT prediction extraction | `model.predict` أعاد Prediction object لا tuple من عنصرين | اختلاف API في PyTorch Forecasting 1.8 | استخدام الحقول `output`, `y`, `index` | التدريب لم يُعد بسبب هذا الخلل |
| Target-year labeling | extraction الأول أضاف سنة واحدة إلى index | index يحتوي decoder/target year بالفعل | إزالة `+1` وإعادة استخراج predictions | القيم والتدريب لم يتغيرا |

## النتيجة

نجحت بوابة v1.1: 3,475 صفاً، 139 كياناً، 11 متغيراً، صفر خلايا مفقودة بعد numeric validation، صفر duplicate windows، وzero target leakage violations. أُجري تدريب TFT مرة ناجحة، ثم استخراج test وإعادة التقييم بعد إصلاح تسمية السنة فقط.

لم تُشغّل stability grid أو ablations أو reverse extraction أو surrogate validation.
