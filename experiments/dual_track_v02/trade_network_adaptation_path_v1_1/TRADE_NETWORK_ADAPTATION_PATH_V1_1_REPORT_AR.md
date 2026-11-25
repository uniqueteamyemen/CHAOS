# تقرير Trade Network Adaptation Path V1.1

## الحكم التنفيذي

نُفذ مسار Event-Path على بيانات IMF IMTS XG الموجودة فعلياً، بعد تجميد عقد V1.1. أتاح تعريف الحدث الأوسع تمثيل الضغط التجاري كحالة متعددة الأبعاد بدلاً من اشتراط خروج top-1 فقط. نتج عن ذلك **170 event rows** عبر **135 reporter** و**3375 reporter-year state rows**.

الحكم النهائي هو **`rejected`**. السبب أن المرشح الحتمي لعائلة التكيف كان أسوأ من خطوط الأساس خارج العينة، رغم أن coverage النهائية بلغت 32 حدثاً عند h=2. لا توجد دعوى سببية، ولم يُفتح CVT، ولم يحصل المسار على وزن إيجابي في Composer أو runtime.

## تصميم المسار

استخدمت التجربة candidate pool ثابتة من عشرة شركاء لكل reporter، مختارة من نافذة 2000–2004. الحالة السنوية حفظت عدد الشركاء المرصودين، مجموع التدفق الخام، هوية top-1، حصة top-1، حصة top-3، high concentration، flow stress، concentration stress، وtop-1 exit. لم تُستخدم imputation أو missing-as-zero أو normalization أو log أو differencing أو smoothing أو تحويل للتواتر.

عُرّف الحدث عندما تكون السنوات السابقة والحالية صالحة، ويظهر high concentration قبل الحدث أو flow stress أو concentration stress أو top-1 exit في سنة الحدث. صُنفت النتائج إلى stable replacement أو diversification أو fragmentation أو failure-to-adapt، مع استبعاد horizon غير القابل للتصنيف بدلاً من ملء الفجوة.

## النتائج المقفلة

| الأفق | train events | final events | reporters | candidate Brier | target-history Brier | state-persistence Brier | previous-state Brier | candidate accuracy |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| h=1 | 112 | 32 | 32 | 0.3750 | 0.1231 | 0.0810 | 0.0824 | 0.2500 |
| h=2 | 112 | 32 | 32 | 0.3281 | 0.1138 | 0.0893 | 0.0880 | 0.3438 |
| h=3 | 112 | 32 | 32 | 0.2813 | 0.0952 | 0.0829 | 0.0899 | 0.4375 |

عند h=2 كان المرشح أسوأ من كل baseline، لا أفضل منها. لذلك فشل شرط Brier، وفشل شرط التحسن في family accuracy، ولا يمكن اعتباره نمطاً تنبؤياً مؤهلاً.

## rolling-origin

استخدمت origins في 2011 و2013 و2015 و2017. تراوح حجم evaluation بين 14 و24 حدثاً حسب الأفق والـorigin، ولم يتحقق شرط 20 حدثاً في كل origin. هذه النتيجة وحدها تمنع ترقية المسار حتى لو تحسن final block.

## null controls

| null | replicate | المتوسط | SD | unique statistics | p lower-tail للميزة |
|---|---:|---:|---:|---:|---:|
| block permutation within reporter | 2000 | 0.3410 | 0.0313 | 2000 | 0.0010 |
| rank-preserving volume null | 2000 | 0.0376 | 0.0066 | 1997 | 1.0000 |
| restricted time placebo | 2000 | 0.0180 | 0.0143 | 1851 | 1.0000 |

الـnulls الثلاثة non-degenerate. نتيجة block وحدها لا تكفي، لأن candidate observed advantage كان موجباً في تعريف Brier advantage، بينما rank-preserving وtime placebo لا يدعمانه، كما أن candidate نفسه كان أسوأ من baselines في final block. لم تستخدم null p-value منفردة لتجاوز فشل المقارنة خارج العينة.

## القرار والقيود المكتشفة

المسار الأوسع نجح في تحويل السؤال من هوية شريك واحدة إلى Outcome Families، ورفع عدد الأحداث من حالة شديدة الندرة إلى 170 حدثاً إجمالياً و32 حدثاً في final block. لكنه كشف أن القاعدة الحتمية الحالية لا تتعلم عائلة التكيف؛ فهي تخلط بين subtype المستنتج من حالة الحدث وبين outcome اللاحق، وتخسر أمام baseline بسيط يلتقط غلبة fragmentation في العينة.

هذا ليس سبباً لإعادة tuning للعتبات بعد رؤية النتائج. النتيجة المسجلة هي أن **Event-Path V1.1 rejected**. تُحفظ الحالة والمسارات والـnulls كأدلة قابلة للتدقيق، لكن لا يجوز تركيبها أو تشغيلها.

تم تشغيل validator وsupervisor وEvidence Graph وcompiler وfinal gate. النتيجة المركزية: graph=`64 nodes / 63 edges`، admitted supported-predictive=`2` قديمة فقط، quarantined=`30`، runtime=`0`، causal claims=`0`، QA=`pass`. لم تتغير البيانات الخام أو baseline أو `market-intelligence-engine`.

القرار التالي ليس إعادة تشغيل V1.1. إذا استمر البحث، فالمطلوب عقد جديد يغيّر طريقة بناء candidate من قاعدة حتمية إلى نموذج fit-only متعدد الفئات مع عقوبة تعقيد، أو مصدر مستقل يتيح shock خارجي حقيقياً. لا ينبغي فتح CVT لهذا المسار الحالي.
