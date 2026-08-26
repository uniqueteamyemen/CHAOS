# سجل التغييرات — استكشاف مسارات الأشجار

## سبب إضافة الأسلوب

الأسلوب الأول كان يبحث في conjunctions محدودة من حالات low/middle/high، ثم لم يتجاوز المرشح الأحادي baseline أو null. أُضيفت أشجار قرار صغيرة لأن الهدف هو استخراج مسارات رمزية متعددة العقد مع عتبات عددية قابلة للقراءة، وليس الاكتفاء بوزن feature أو attention.

## الاختبارات المضافة

| الاختبار | سبب الإضافة | النطاق | الحالة |
|---|---|---|---|
| `reverse_extraction_tree_v1_exploratory` | اكتشاف تفاعلات عتبات ومسارات مركبة عند horizons أطول | 72 نموذجاً: عائلتان × 3 horizons × وضعان × 3 أعماق × seedين | مكتمل |
| `reverse_extraction_tree_maxstat_null_v1` | تصحيح حقيقة أن أفضل مسار اختير من شبكة واسعة | 2,000 label-permutation replicates، max-stat على 72 نموذجاً | مكتمل |
| `tree_grid_null_suite` | اختبار robustness ضد nulls مختلفة | 500 replicate لكل label/support/cyclic على الشبكة كاملة | مكتمل، ميزانية مخفضة ومسجلة |
| `tree_target_history_baselines` | فصل الإشارة الخارجية عن تاريخ الهدف | أشجار target-only بنفس depths/seeds/horizons | مكتمل |
| `tree_rolling_stability_v1` | معرفة هل الصيغة تتكرر عبر نوافذ زمنية مختلفة | 3 folds قبل locked test | مكتمل |

## التغييرات المنهجية المقصودة

أُسند split حسب سنة النتيجة `target_year=t+h` لا حسب سنة origin فقط. هذا يمنع تسمية نتائج horizons الأطول ضمن split زمني خاطئ. بقي locked test 2020–2024 خارج الاختيار والتقييم، ولم تُعدّل raw data.

## النتائج المختصرة

ظهر مرشح قوي نسبياً لعائلة `material_drop_2pp` عند `h=3`: نمو الهدف الحالي أكبر من نحو 4.96، مع شرط سكاني عند `t-2`، وحقق validation BA=`0.6354` وF1=`0.3878`. تجاوز أفضل target-history tree في نفس العائلة BA=`0.5784` وF1=`0.2787`، كما تجاوز max-stat null في التجارب المحفوظة.

لكن المسار الحرفي لم يتكرر في كل rolling fold؛ لذلك بقي `promising descriptive candidate` ولم يُرقَّ إلى validated pattern أو operational algorithm.
