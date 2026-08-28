# Gulf of Aden Seismic Transfer Test v1 — Repaired Predictor

هذا هو نفس اختبار النقل السابق بعد إصلاح ميكانيكية التنبؤ. لم تتغير بيانات USGS أو عقد النطاق أو تعريف الحالات أو `window_width=3` أو `train_size=8` أو المصدر. أصبح المسار الآن يجمّد العلاقة الشرطية داخل train ويطبق `min_support=2`؛ المسارات غير المدعومة تمتنع بدل استخدام persistence fallback.

- Source: `data/raw/seismic_gulf_of_aden_v1/usgs_gulf_of_aden_query.geojson`
- Fixed region: 10–15°N, 42–52°E
- Fixed period: 2000-01-01 through 2024-12-31 UTC
- Fixed threshold: magnitude ≥ 4.5
- Events retained: **408**
- OOS rows: **400**

## Metrics on supported-path rows

| Model | Accuracy | N | Coverage |
|---|---:|---:|---:|
| Repaired Event-Path | 0.3271 | 269 | 0.6725 |
| Majority baseline | 0.2454 | 269 | 0.6725 |
| Persistence baseline | 0.0855 | 269 | 0.6725 |

الامتناع كان في `131/400` حالة، بمعدل **0.3275**. لذلك لا يصح عرض `0.3271` كدقة على كامل السجل؛ إنها دقة على الحالات التي اجتازت دعم المسار، مع coverage معلنة.

## Interpretation

الإصلاح رفع الفصل بين Path model وMajority على الصفوف المدعومة إلى Lift قدره `0.0818`، لكنه لا يحول النتيجة تلقائيًا إلى دليل مستقر. يجب قراءته مع coverage والـNull المجدد. لا يوجد tuning زلزالي، ولا تُستخدم هذه النتيجة لتعديل النموذج الاقتصادي.

## Status

`provisional_transfer_only`

النتيجة لا تزال نقلًا أوليًا، وليست دليلًا سببيًا أو إشارة قابلة للنشر.
