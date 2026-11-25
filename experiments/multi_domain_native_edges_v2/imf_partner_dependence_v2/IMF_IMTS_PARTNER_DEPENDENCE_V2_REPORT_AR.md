# تقرير IMF IMTS Partner Dependence V2

## الملخص التنفيذي

تم توسيع مسار IMF IMTS فوق baseline السابق دون تعديل عقد V1 أو حذف نتائجه. شمل الاقتناء الموسع 139 reporter مستوفياً لشرط هدف WDI، وأعاد API الرسمي 139 استجابة HTTP 200 لمؤشر صادرات السلع السنوي `XG_FOB_USD` للفترة 2000–2024، بإجمالي خام بلغ 311,818,266 بايت. بعد تطبيق شرط candidate pool الكامل، دخل الاختبار 135 reporter فقط، ولكل واحد عشرة شركاء مرشحين وخمسة شركاء نشطين. بُنيت 2,295 reporter-year observations، واختُبرت عائلة الاعتماد والقيمة والتركيب مع ضوابط partner-identity null وoutcome null وtime placebo وregion holdout.

مرّ شرط coverage الأساسي، إذ ظهرت 77 حالة تعرض في confirmation لدى 48 reporter عبر سبع مناطق. لكن فرق المخاطر الأساسي كان سالباً في الآفاق الثلاثة: `-0.1493506` عند سنة، `-0.2164502` عند سنتين، و`-0.1212121` عند ثلاث سنوات. وكان `partner-identity null` غير degenerate بالفعل، لكنه أعطى `p=0.9884012`، بينما أعطى outcome null `p=0.9994001` وtime placebo `p=0.9992002`. لذلك سُجلت النتيجة `rejected` وفق العقد V2، دون وزن إيجابي في Composer ودون runtime promotion ودون causal claim.

## ما تم توسيعه

| العنصر | V1 السابق | V2 الحالي |
|---|---:|---:|
| reporters المكتسبة | 15 | 139 استجابة XG رسمية |
| reporters ذات candidate pool مكتمل | 15 | 135 |
| candidate pool لكل reporter | 5 | 10 |
| active partner set | 5 | 5 من أصل 10 |
| نافذة اختيار الشركاء | 2000–2004 | 2000–2004، ثابتة |
| fit | 2005–2013 | 2005–2013 |
| validation | 2014–2018 | 2014–2017 |
| confirmation | 2019–2021 | 2018–2021 |
| flow primary | bilateral contraction | bilateral contraction |
| composition diagnostic | غير موجود | partner-share loss |
| region holdout | غير موجود | World Bank region leave-one-out |

تم استخدام WDI GDP فقط كهدف لاحق وكشرط توفر أولي للـreporter، ولم يُستخدم لتحديد أفضل الشركاء أو اختيار threshold أو اختيار النتيجة.

## الاقتناء والبروڤنانس

أُجريت محاولة أولى بطلب XG وMG معاً و`limit=100000`. أعاد endpoint الرسمي `403` لكل الطلبات وعددها 139، من دون exception برمجي؛ سُجلت هذه الاستجابة كفشل وصول ولم تُعامل كبيانات. أُجريت بعد ذلك محاولة بديلة محدودة إلى XG فقط مع `limit=5000` ومرجع بطاقة IMF الرسمي؛ أعادت جميع الطلبات وعددها 139 الحالة `200`.

بلغ إجمالي الخام في الاستخراج البديل `311,818,266` بايت، وحُفظت كل استجابة في ملف مستقل مع URL وheaders وSHA-256. بقي الخام خارج Git وفق سياسة المشروع. جُمعت الاستجابات في artifact مشتق حجمه نحو 128 MB مع SHA:

```text
a5fdda798b44806eb7a97c461888d516b44b54bc7de763a4f9b6a5b6cebd6906
```

لم يُستخدم MG في V2 لأن المسار الأساسي الجديد يختبر بنية اعتماد الصادرات وشريك الصادرات فقط؛ وهذا يحافظ على فصل المؤشرات ولا يخلط حالة نقص MG السابقة مع XG.

## تعريف الاختبار

اختيار الشركاء تم على مستوى كل reporter من متوسط حصة الصادرات الخام خلال 2000–2004، بعد استبعاد الأكواد التجميعية و`G001=World` كمرشح شريك. تم تثبيت أعلى عشرة شركاء كـcandidate pool، ثم أعلى خمسة كـactive set. لا تُستخدم نتائج GDP في هذه الخطوة.

الحالة الأساسية هي:

```text
top-three candidate-pool baseline share >= 50%
AND
at least one active bilateral export value falls below 70% of its value in t-1
→ WDI GDP growth at t+h <= GDP growth at t - 2 percentage points
```

اختُبرت `h=1,2,3`. لم يُعامل missing على أنه صفر، ولم تُحوّل السلاسل اليومية أو الشهرية، ولم تُطبق log أو differencing أو normalization أو imputation.

## النتائج

### primary interaction

| الفترة | h=1 | h=2 | h=3 |
|---|---:|---:|---:|
| Fit risk difference | -0.1427747 | -0.1918132 | -0.1510714 |
| Validation risk difference | 0.0773036 | -0.0094826 | -0.1034838 |
| Confirmation risk difference | -0.1493506 | -0.2164502 | -0.1212121 |
| Confirmation exposure rows | 77 | 77 | 77 |
| Confirmation exposed reporters | 48 | 48 | 48 |

الاتجاه ليس مستقراً بين الفترات، وينتهي سالباً في confirmation في الآفاق الثلاثة. كما أن variants `top1_value` و`top5_value` أعطت نفس نتيجة bilateral value في هذه العينة، لأن حالات dependence تغطي عملياً نفس reporters. أما variant `top3_share_interaction` فكانت موجبة هامشياً عند h=3 (`0.0038043`) لكنها diagnostic فقط، ولا تتجاوز أي null أو promotion gate.

### الضوابط

| الضابط | النتيجة | القرار |
|---|---:|---|
| partner-identity null | `p=0.9884012`, SD=`0.0232753`, 715 قيمة فريدة | غير degenerate لكنه فشل |
| outcome null | `p=0.9994001` | فشل |
| time placebo | `p=0.9992002` | فشل |
| cluster bootstrap | mean=`-0.1052483`, 95% interval=`[-0.1676048,-0.0379735]` | يظل سالباً |
| region holdout | PASS، سبع مناطق | لا ينقذ الإشارة السلبية |
| concentration | أقصى reporter=`5.06%`، أقصى partner=`18.06%` | PASS |
| stability | FAIL | لا يوجد اتجاه موجب مستقر كافٍ |

قيمة `p=0.9884012` في identity null ليست بسبب degeneracy هذه المرة؛ فالضابط أنتج 715 قيمة إحصائية فريدة وانحرافاً معيارياً موجباً. وهي لذلك نتيجة سلبية فعلية لهذا السؤال: إعادة تعيين هوية active partner داخل candidate pool لا تجعل النتيجة الحقيقية مميزة.

## حالات التشغيل المصححة

فشل طلب XG+MG الموسع بـ403 وسُجل كفشل وصول، ثم نجح مسار XG-only الرسمي. كما أن النسخة الأولى غير المتجهة من المشغل بقيت 13 دقيقة دون artifacts نهائية، فأُوقفت واستُبدلت بنسخة متجهة تحفظ نفس contract وseeds والإجراءات. ظهر أثناء التدقيق أن selection register يضم reporter واحداً بخمسة شركاء فقط؛ صُحح المشغل ليستبعده من الاختبار، ثم أُعيد التشغيل على 135 reporter المتوافقين مع شرط العشرة. لا يُعتبر أي تشغيل سابق غير متوافق نتيجة نهائية.

## قرار Evidence Library

النتيجة النهائية هي:

```text
edge_status = rejected
causal_claim = false
runtime_eligible = false
positive_composer_weight = false
```

هذا الرفض لا يعني أن كل اعتماد تجاري أو كل صدمة شريك بلا أثر اقتصادي. يعني فقط أن الصيغة المحددة مسبقاً في V2 — اعتماد candidate-pool مع bilateral export contraction والتنبؤ بتدهور GDP وفق هذا الهدف والزمن — لم تقدم دليلاً تنبؤياً مستقلاً في هذه العينة، رغم أن coverage والـregion holdout أصبحا كافيين.

لا أوصي بإعادة تشغيل V2 نفسها بتغيير threshold بعد رؤية النتائج. إذا استمر البحث، يجب أن يتغير السؤال: مثلاً بنية partner-share loss، أو asymmetry بين export dependence وimport dependence، أو source-native partner substitution. وكل واحد منها يحتاج contract جديداً مستقلاً وتصحيحاً عائلياً مسبقاً.

## المخرجات الرئيسية

تم حفظ العقد، profile universe، ملخص الاقتناء، observation profile، observation-shards manifest، selection register، exclusion register، reporter-year panel، metrics، reporter stability، region holdout، null summaries، run manifest، وTransitionEvidence V2. أضيفت النتيجة إلى Controlled Pattern Registry كـ`rejected`، وأضيفت إلى Evidence Graph دون وزن إيجابي.

بعد إعادة تشغيل سلسلة الحوكمة، كانت النتيجة: `57` graph nodes، و`58` graph edges، منها `2` supported-predictive records قديمة فقط، و`27` records في quarantine، و`0` runtime-eligible، و`0` causal claims. اجتاز final supervisor gate والـQA manifest الفحص بحالة `pass`، ويحتوي QA manifest على `114` artifact قابلاً للـhash. النتيجة الجديدة V2 لا تدخل shared composition.

## References

[1]: https://data.imf.org/en/datasets/IMF.STA:IMTS "IMF International Trade in Goods by partner country (IMTS)"

[2]: https://api.imf.org/external/sdmx/3.0/structure/dataflow/IMF.STA/IMTS/1.0.0?detail=full&references=all "IMF SDMX IMTS dataflow structure"

[3]: https://api.worldbank.org/v2/country?format=json&per_page=400 "World Bank Country API"

[4]: https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG "World Bank GDP growth indicator"
