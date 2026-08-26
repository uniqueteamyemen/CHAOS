# CHAOS — تقرير حملة الوكلاء المتوازيين، الجولة الثانية

## نطاق الجولة

هذه الجولة تستخدم `RESEARCH_SNAPSHOT_V3` كمرجع ثابت، وتوسّع Evidence Library في Trade وInstitutions/Policy بالتوازي مع تشغيل مسارات Energy وEnvironment/Disasters وHealth/Pandemics. لم تُعد التجارب القديمة أو تُفتح locked tests، ولم يُعدّل `market-intelligence-engine`.

## الوكلاء والمدخلات

| الوكيل | المدخل الفعلي | التواتر | المخرج |
|---|---|---|---|
| Trade / Comtrade | 125 طلباً محدوداً لخمسة reporters، 124 استجابة 200 وحالة timeout واحدة | annual | states محدودة؛ `not_testable` للشبكة التجارية |
| Trade / WDI | WDI bulk موجود مسبقاً خارج CHAOS، خمس سلاسل trade منفصلة، 29,004 مشاهدة | annual | 29,004 Trade DomainStates، 259 كياناً، 2000–2024 |
| Institutions/Policy / WGI | WGI 2025 الرسمي، 1,296 indicator rows | annual source-defined years | 32,403 institutional DomainStates، 216 كياناً، 1996–2024 |
| Energy | EIA annual matrix السابقة | annual | لا edge جديدة موجبة |
| Environment/Disasters | USGS scoped earthquake events | event | 1,141 event states؛ لا production shock أو recovery مستنتج |
| Health/Pandemics | WHO COVID daily release | daily | 573,360 خاماً و215,751 states reported؛ لا annual dummy |

## النتائج التجريبية

اختُبرت WDI Trade openness squeeze داخل المجال عند lead 1 و2. أعلى BA=`0.6943799948` ظهر في validation، لكنه لم يتكرر في confirmation، ولم يفصل عن max-stat null: `p=0.4547726137`. لذلك سُجلت الحافة `rejected_by_current_maxstat_null`.

واختُبر مسار عابر جديد: WDI trade squeeze عند `t` إلى material GDP deterioration عند `t+1..t+3`. كانت التغطية الفعلية بين `2,830` و`3,089` صفاً حسب الأفق، وأعلى BA=`0.5348039216`، لكن max-stat `p=0.5897051474` مع فشل confirmation. المسار مرفوض، ولا يجوز استخدامه كوسيط إيجابي.

في WGI، أظهرت بعض مقاييس continuity BA أعلى من 0.5، لكن بوابة support كشفت أنها persistence ناتجة عن prevalence مرتفع لا Edge جديدة. أما decline فكان نادراً أو degenerate في splits. النتيجة: `5` حواف rejected و`5` not_testable، ولا توجد policy shocks أو leader-specific deviations مستنتجة من WGI composite.

## بوابة المشرف

بعد توحيد DomainState وTransitionEvidence schemas، أُعيد تشغيل validators وEvidence Graph وPattern Compiler وبوابة الأهلية النهائية:

```text
DomainState schema: pass
TransitionEvidence schema: pass
admitted supported_predictive records: 2
quarantined records: 22
graph: 41 nodes / 46 edges
runtime-eligible patterns: 0
causal claims admitted: 0
```

القاعدة المركزية فعالة: لا تدخل `rejected` أو `unresolved` أو `not_testable` أو `provisionally_supported_descriptive` إلى التركيب بوزن موجب. وجود الحافة في الرسم يعني أنها محفوظة للمراجعة، لا أنها مؤهلة للـComposer.

## الأخطاء والقيود الموثقة

أُصلحت مطابقة DomainState schema في WGI وTrade وWHO وUSGS بعد اكتشاف استخدام `regime_probability` بدلاً من `state_probability` وغياب حقول `pattern_id` و`lead_profile` و`edge_status`. كما أُصلحت أخطاء أولية في Comtrade rate limiting وفي adapter أسماء الأعمدة، وأعيدت الاختبارات بعد كل تصحيح.

Comtrade الحالي ليس bulk network؛ هو bounded preview ومفيد لإثبات الوصول والبنية فقط. WDI Trade أصبح panel قابلاً للتحليل، لكنه aggregate indicators وليس reporter×partner×commodity network. لذلك لا تكفي نتيجته الحالية لتعريف trade disruption أو mechanism.

## قرار الجولة

لا توجد Edge جديدة مؤهلة للتركيب أو التشغيل. أقوى نتيجة ما زالت المرشح الاقتصادي الوصفي السابق، وليس مساراً تجارياً أو مؤسسياً أو جيوسياسياً جديداً. الخطوة التالية المنطقية هي إما بناء مصدر تجارة متعدد الأبعاد بحدود مقبولة، أو الحصول على مصدر policy observations مؤرخة يسمح بفصل policy shock عن WGI. لن يُبنى Composer أكبر قبل نمو مكتبة الأدلة المؤهلة.
