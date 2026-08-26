# CHAOS — تقرير التنفيذ المتوازي الحالي

## القرار التنفيذي

تم تطبيق ملاحظة المستخدم: لم تُبنَ Ledger وTemporal Alignment وEvidence Graph وPattern Compiler كمرحلة هندسية طويلة، بل أُنشئ الحد الأدنى القابل للتشغيل بالتوازي مع البحث التجريبي عن حواف جديدة. لا توجد أي تغييرات في `market-intelligence-engine`، ولم تُرقَّ أي نتيجة إلى production.

## ما أُنجز في هذه الجولة

| المسار | التنفيذ | النتيجة |
|---|---|---|
| Research Ledger | عقد JSONL وأداة append-only مع hashes وسجلات للعقود والتجارب والمخرجات | أضيفت سجلات العقود، المحاذاة، Edges، adapters، graph، والـcompiler |
| Temporal Alignment | عقد يمنع التحويلات الضمنية وفحص annual-to-annual للمصفوفة الحالية | 3,475 صفاً، 139 كياناً، 25 سنة كاملة، صفر صفوف مستبعدة في التدقيق السنوي |
| Within-domain Edges | تضخم مرتفع، ضغط الحساب الجاري، زيادة كثافة الطاقة مقابل material deterioration عند h=1..3 | لا edge جديد فصل عن max-stat null؛ أعلى BA=`0.5471558169`، p=`0.3013493253` |
| WHO Adapter | مصدر WHO COVID daily release، دون تحويله إلى annual | 573,360 صفاً خاماً، 215,751 صفاً يحوي بلاغ حالة/وفاة، 239 كياناً، 2020-01-04 إلى 2026-07-19 |
| USGS Adapter | مصدر USGS FDSN Earthquake Catalog، event-native | 1,141 حدثاً magnitude≥6.5، 2000-01-08 إلى 2024-12-27 |
| Native DomainStates | WHO daily وUSGS event محفوظان بتواترهما الأصلي | لا production shock مستنتج، ولا country matching للـUSGS |
| Cross-domain Edge جديد | economic deterioration عند t → UCDP state-based conflict عند t+1..t+3 | joined=`1,962` صفاً، `56` كياناً، أعلى BA=`0.5201013514`، p=`0.4532733633`؛ مرفوض حالياً |
| Evidence Graph | دمج TransitionEvidence القديم والجديد والسجل المتحكم وحواف native غير القابلة للاختبار | `23` عقدة و`23` حافة، `0` ادعاء سببي، وحالتا WHO/USGS محفوظتان كـ`not_testable` |
| Pattern Compiler | تجميع الحواف `supported_predictive` فقط، وحفظ النمط الوصفي المبدئي منفصلاً | `0` runtime-eligible، و`1` provisional research-only candidate، و`11` مستبعدة من التركيب الإيجابي |

## النتيجة العلمية الحالية

لم يظهر في هذه الجولة نمط جديد صالح للترقية. المرشح الاقتصادي السابق `high current GDP growth (>4%) → material GDP deterioration within 3 years` ما زال في وضع `provisionally_supported_descriptive` فقط. لا تدخل الحواف المرفوضة أو غير المحسومة بوزن موجب في Composer، ولا تُستخدم الحالات اليومية أو الحدثية كبديل عن outcome سنوي.

المسار الجديد `economic deterioration → UCDP conflict` لم يتجاوز null. هذه نتيجة مهمة لأنها تختبر وسيطاً اقتصادياً مختلفاً عن الحافة المرفوضة سابقاً `high-growth → conflict`، ولذلك لا يجوز إعادة وصف فشل الحافة القديمة أو الجديدة كنجاح جيوسياسي غير مباشر.

## حدود مصادر WHO وUSGS

بيانات WHO محفوظة كبيانات يومية حسب `Date_reported`، مع إبقاء الخانات الفارغة فارغة وعدم تحويلها إلى صفر. توثق provenance أن التعريفات وممارسات الإبلاغ والتعديلات اللاحقة تختلف بين البلدان. بيانات USGS محفوظة كأحداث ذات وقت وإحداثيات وخصائص زلزالية؛ الاستعلام الحالي مقيد بـ`minmagnitude=6.5` ولا يتضمن إسناداً بلدياً. لذلك أُنشئت DomainStates أصلية فقط، وسُجل أي event-to-annual GDP edge كـ`not_testable`.

## خطأ تنفيذي اكتُشف وصُحح

في التشغيل الأول لاختبار Edges الاقتصادية، كانت دالة التنفيذ تعيد استخدام آخر قناع تنبؤ للحواف الثلاث، فظهرت مقاييس متطابقة. أُوقف الاعتماد على تلك الجولة، وصُحح السكريبت ليحسب قناع كل edge داخل loop ثم أُعيد تشغيل التجربة كاملة. كما صُححت فهرسة permutation بعد اكتشاف أن فهارس مجموعات البلدان لم تكن متوافقة مع مصفوفة NumPy. الأرقام الواردة في هذا التقرير هي أرقام التشغيل المصحح فقط.

## حالة الترقية

`Pattern Compiler` ليس محرك إنتاج. لا توجد patterns runtime-eligible في هذه الجولة. يبقى Research Runtime Sandbox السابق معزولاً research-only، ولا يحصل على WHO أو USGS قبل اكتمال محاذاة ومطابقة كيانات وقياس صدمة الإنتاج والتعافي. كما لم تُستخدم هذه الجولة لتعديل threshold أو إعادة تدريب TFT أو إعادة فتح locked test.

## الملفات الأساسية

توجد العقود في `experimental_contracts/`، ونتائج Edges الاقتصادية في `experiments/macro_plus_eia_energy/within_domain_edges_v1/`، ونتائج المسار الاقتصادي–الصراعي في `experiments/multi_domain_native_edges_v1/`، وحالات WHO/USGS في `experiments/multi_domain_native_adapters_v1/`، وEvidence Graph وPattern Compiler في `experiments/macro_plus_eia_energy/evidence_graph_v1/` و`pattern_compiler_v1/`، والسجل في `research_ledger/RESEARCH_LEDGER_V1.jsonl`.

## القرار التالي

يستمر العمل من Evidence Library لا من Composer كبير: نحتاج حوافاً جديدة داخل المجالات ذات تعريفات مصدرية واضحة، ثم اختبارات OOS وentity holdout وnull. أما ربط WHO أو USGS بالاقتصاد فيحتاج عقد محاذاة مستقل قبل أي اختبار، ولن يُسمح بتحويله إلى annual dummy أو مسار إيجابي لمجرد أن السردية معقولة.
