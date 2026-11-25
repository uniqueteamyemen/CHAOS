# تقرير Discovery Track — IMF IMTS Partner Substitution V3

## الحكم

أنتجت تجربة V3 مرشحاً واعداً لاستمرار هوية الشريك البديل بعد إزاحة الشريك الأول في خط أساس 2000–2004، لكنها **لم تُرقَّ إلى `supported_predictive` ولم تُفتح لها Causal Validation**. الحالة الحالية هي `candidate_promising_but_not_admitted`، وسُجلت في TransitionEvidence وControlled Pattern Registry كـ`unresolved` حتى تبقى خارج Composer والـruntime.

## السؤال والتصميم

السؤال مختلف عن IMTS V2 المغلق: بعد أن يختلف الشريك صاحب أعلى قيمة صادرات عن baseline top-1، هل يستمر الشريك البديل صاحب top-1 في السنوات اللاحقة أكثر مما يتوقعه null يحافظ على عدد السنوات المؤهلة وتوزيع هويات الشركاء داخل reporter؟ لم تُستخدم GDP outcomes، ولم يُعد اختيار candidate pool بعد رؤية النتائج.

استُخدم نفس سجل candidate pool المقفل في V2، لكن دخل الاختبار فقط reporters الذين يملكون عشرة شركاء كاملي السجل، أي `135` reporter. حُددت نافذة discovery في `2005–2014` ونافذة confirmation المقفلة في `2015–2024`. الصفوف التي ينقص فيها أي شريك من العشرة بقيت missing واستُبعدت من السنة؛ لم تُفسر كصفر.

## النتائج الرقمية

| النافذة | الأفق | أحداث الإزاحة المؤهلة | reporters | persistence rate |
|---|---:|---:|---:|---:|
| Fit | 1 سنة | 200 | 40 | 0.8550 |
| Fit | 2 سنتان | 200 | 40 | 0.7750 |
| Fit | 3 سنوات | 200 | 40 | 0.7150 |
| Confirmation | 1 سنة | 310 | 49 | 0.8613 |
| Confirmation | سنتان | 271 | 49 | 0.7712 |
| Confirmation | 3 سنوات | 235 | 49 | 0.6979 |

في confirmation كان فرق persistence عن identity-sequence null موجباً عند h1/h2/h3: `0.0845`، `0.1254`، `0.1318`، مع identity-null p-values حدها الأدنى التجريبي `0.0001` عند كل أفق. وكان time-placebo sequence-shift p-value `0.0002` عند كل أفق. أظهر null توزيعات غير منهارة: الحد الأدنى لعدد الإحصائيات الفريدة عبر seeds كان `304` للـidentity null و`156` للـtime placebo عند h1.

هذه الأرقام تجعل المرشح **مثيراً للاهتمام**، لكنها لا تثبت آلية سببية. قد يكون جزء كبير من الإشارة ناتجاً عن استمرارية شبكات التجارة وخصائص الرتب نفسها؛ لذلك لا يكفي identity permutation وحده لقبول Edge تشغيلية.

## Stability والتدقيق

شُغلت Stability Grid بخمسة seeds محددة مسبقاً: `271108–271112`. بقيت معدلات confirmation المرصودة ثابتة تماماً لأن الإحصاء المرصود حتمي، وتحركت متوسطات null ضمن نطاق ضيق. بلغ أعلى تركّز لأحداث confirmation نحو `2.98%` عند h3، ولم يهيمن reporter واحد على النتيجة.

اكتُشف قبل اعتماد التشغيل خطآن في التشغيل الأول: دخول reporter `WSM` رغم أن candidate pool لديه تسعة شركاء فقط، وتكرار diagnostic top-3 لآلية primary top-1. أُوقف تفسير التشغيل الأول، وصُحح الكود، وأعيد التشغيل؛ الناتج الحالي مبني على `135` reporter وعلى diagnostic top-3 منفصل. سُجلت الواقعة في `IMF_IMTS_PARTNER_SUBSTITUTION_V3_RUN_CORRECTION_NOTE_V1.json`.

## سبب عدم الترقية

العقد المجمد V3 لم يحدد صراحة alpha وFDR وقاعدة pass النهائية لهذه العائلة، كما أن null الحالي يختبر ترتيب الهوية وتوزيعها لكنه لا يمثل كل نماذج الاعتماد الزمني الممكنة. لهذا لا يجوز استخدام p-values الحالية كترخيص رجعي للترقية. يلزم قبل أي admission عقد أو erratum جديد يحدد null أقوى يحافظ على temporal dependence أو run structure، وقاعدة تعدد اختبارات، وentity/region holdout، ثم تشغيل مستقل لا يعيد تفسير هذه النتيجة بعدياً.

لا يوجد حالياً shock assignment موثوق في هذا السؤال، لذلك `causal_validation_status=not_run` هو القرار الصحيح. عدم فتح CVT هنا ليس فشلاً في التنفيذ؛ بل منع لفرض تصميم سببي على سؤال network persistence لا يملك treatment خارجي محدداً.

## الحوكمة

مر TransitionEvidence V3 عبر schema validation، وسُجل في Evidence Graph كـ`unresolved`. بقيت قواعد graph كما هي: positive Composer input status الوحيد هو `supported_predictive`. لا causal claims، ولا runtime eligibility، ولا تعديل لـ`market-intelligence-engine` أو للـbaseline أو للبيانات الخام.

القرار النهائي لهذه الجولة: **مرشح واعد مغلق مؤقتاً، لا Edge مؤهلة**. إذا استمر البحث، فالمسار الصحيح هو عقد V3.1 أو V4 مستقل مع null زمني أقوى وسؤال محدد، وليس إعادة tuning لهذه النتيجة.
