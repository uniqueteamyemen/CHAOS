# USGS Catalog Integrity V1 — P2.2

**الحالة:** تنفيذ نزاهة إدخال/تصفية، وليس اعتماداً لكتالوج زلزالي مكتمل أو نموذج null أو كاشف زلازل.  
**فرع التنفيذ الانتقائي:** `fix/usgs-catalog-integrity-main-v1`  
**الأساس:** `main-phase2@b838eb48b2040bf358fc216e1e004311edfc30e8`  
**المصدر التاريخي للمنهج:** `fix/p2-2-3-usgs-catalog-integrity-v1`، من دون دمج تاريخه المتفرع أو تجاربه كاملة.

## 1. ما يضيفه التغيير

يُعاد التحقق من كل USGS feature قبل إدخاله في السلسلة التحليلية:

- إحداثيات رقمية منتهية، ضمن المجال الجغرافي العالمي، وداخل حدود الحزام المحدد؛ مع دعم الحزام الذي يعبر خط التاريخ الدولي.
- magnitude رقمية منتهية وتساوي أو تتجاوز عتبة الاستعلام.
- event time صحيح بصيغة epoch milliseconds صحيحة/عدد صحيح، داخل نافذة التحليل UTC نصف المفتوحة `[Y0-01-01, (Y1+1)-01-01)`.
- رفض bool وNaN وInfinity والقيم الزمنية الكسرية، وعدم تحويلها إلى أحداث صالحة.

تُحفظ الاستجابة الخام في مسار snapshot الحالي مع SHA-256 وبيانات الطلب. السجلات الملوثة تُسجل في quarantine manifest ولا تدخل الكتالوج المشتق.

## 2. الهوية والتكرار

- معرف الحدث الأصلي من USGS هو المفتاح الأول.
- عند غياب المعرف، يُستخدم fallback حتمي من قيم المصدر المتاحة؛ لا يُستخدم ترتيب الوصول أو رقم تشغيل الوكيل.
- تكرار مطابق تماماً يُسجل في `duplicate_features_deduplicated` ولا يُكتب كسجل ثانٍ.
- تعارض المحتوى تحت event ID واحد لا يستبدل السجل الأول؛ السجل المتعارض يُحجر بسبب `DUPLICATE_EVENT_ID_CONFLICT`.
- يفرض الفحص المحاسبي:
  `events_received = events_accepted + events_quarantined + duplicate_features_deduplicated`.
  أي انحراف يوقف تكوين الكتالوج بدلاً من إصدار manifest ناقص.

## 3. provenance لمقياس الزلزال

تُحفظ قيم `magType` و`magSource` الأصلية في كل صف مقبول، وتُسجل توزيعاتها في ملخص كل حزام، بما فيها العدد المفقود ومؤشرات التجانس.

**قاعدة عدم الخلط:** لا يجوز جمع أو دمج magnitude-frequency distributions ذات أنواع magnitude مختلفة لمجرد أنها رقمية. وجود أكثر من `mag_type` أو missing value يفرض مراجعة معايرة منفصلة قبل أي FMD أو completeness assessment.

## 4. ما لا يثبته هذا التغيير

- لا يحسب `Mc(t, region)` ولا يعتمد magnitude of completeness.
- لا يثبت أن الحد الأدنى للاستعلام هو عتبة اكتمال تاريخية.
- لا يعتمد Gardner–Knopoff أو Zaliapin–Ben-Zion بوصفه declustering صحيحاً إقليمياً.
- لا ينفذ أو يعتمد ETAS/Hawkes أو inhomogeneous Poisson null.
- لا يحول homogeneous Poisson exploratory benchmark إلى seismic null صالح أو detector FPR.
- لا يثبت سبباً أو تنبؤاً أو إنذاراً تشغيلياً.

تبقى حالة الكتالوج `catalog_integrity_status` وصفاً لفحوص الإدخال والحجر فقط. اكتمال المصدر/الشبكة الزمنية/المكانية ومعايرة المقياس مسائل مستقلة.

## 5. الاختبارات

يضيف `real_data_stress_pipeline/tests/test_usgs_catalog_integrity.py` اختبارات لوظائف spatial/magnitude/time validation، حدود antimeridian، حفظ الخام والبصمة، أنواع magnitude/source المختلطة، identical duplicates، event-ID conflicts، ومعادلة محاسبة جميع features.

تعمل الاختبارات ضمن Workflow `real-data-stress.yml` في Pull Request. حدث PR يشغّل contract/unit tests فقط؛ ولا يشغّل ضغط P2.2 الطويل أو ينشر Release.

## 6. حدود التغيير

لا يُعدل `structural_engine/isolated_break_detector_v1/**` أو `experiments/**`. لا تتغير معادلات BreakDetectorV1 أو ثوابته. يتم port لوظيفة سلامة الكتالوج فقط إلى نقطة دخول P2.2 الحالية؛ أما null/declustering audit وعقوده وتقاريره فتبقى مسار مراجعة منفصلاً حتى اجتياز تقييمها المستقل.
