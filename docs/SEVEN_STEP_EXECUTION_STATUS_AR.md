# CHAOS — حالة تنفيذ الخطوات السبع الأصلية

## الغرض

هذا التقرير يعيد ربط العمل الحالي بالخطوات السبع التي اقترحها CHAOS أصلاً. التوسعة الأخيرة لا تستبدل هذه الخطة؛ بل تضيف مجالات الكوارث والجوائح والمؤسسات والسياسة داخل طبقة الـDomain Adapters وState/Path Dictionary، مع احترام التواتر الأصلي وعدم اختلاق أدلة غير متاحة.

## النتيجة التنفيذية

الخطوات السبع نُفذت على مستوى المختبر البحثي بالقدر الذي تسمح به البيانات والأدلة الحالية. النمط الوحيد الذي بقي مدعوماً هو `high current GDP growth (>4%) → material GDP deterioration within 3 years` بوصفه **مرشحاً تنبؤياً وصفياً مدعوماً مبدئياً**، وليس علاقة سببية ولا قاعدة تشغيلية. أما الربط المباشر من النمو المرتفع إلى الصراع فقد رُفض في الاختبار الحالي، وبقي مسار العنف مرتفع الوفيات غير محسوم. لم تُرقَّ الكوارث أو الجوائح أو المؤسسات والسياسة إلى أدلة إيجابية لأن عقود المصادر/التغطية اللازمة لها لم تكن مكتملة داخل CHAOS.

## حالة الخطوات

| الخطوة | ما نُفّذ فعلياً | الحالة والحدود |
|---|---|---|
| 1. Snapshot وPattern Status | ثُبّتت نتائج TFT، الاستقرار، الإزالات، target-history، Reverse Extraction، AMA، UCDP، mediator، وComposer في `RESEARCH_SNAPSHOT_V2.json` والسجل المتحكم | مكتملة. النمط الاقتصادي وصفي مبدئي؛ لا causal promotion |
| 2. Domain Adapters | طبقة DomainState الاقتصادية والصراعية موجودة؛ أضيفت عقود المجال متعدد المصادر وعقد Sandbox. عُرّفت حالات Event/Production Shock/Recovery وPandemic وPolicy دون ادعاء توفر بياناتها | مكتملة جزئياً حسب الجاهزية. الكوارث/الجوائح/السياسة `not_testable` إلى حين اعتماد مصدر وadapter حقيقي |
| 3. State/Path Dictionary | أضيف `STATE_PATH_DICTIONARY_V1.json` مع شروط الدخول والخروج، التواتر، ومتطلبات المحاذاة. أُدخل المسار `Event → Production shock → Recovery` صراحة | مكتملة كعقد بحثي؛ بعض الحالات مرشحة وليست أدلة |
| 4. Economic Replication 2 | تكرار مستقل على UN AMA: validation BA=0.732527 وF1=0.618462؛ confirmation BA=0.682099 وF1=0.503778؛ within-country permutation 2,000 أعطى p=0.0005 في المرحلتين | مكتملة كـindependent-source descriptive replication. لا تعني تجانس AMA أو السببية |
| 5. Cross-Domain Mediator Paths | جُرّب energy/GDP عند t+1 وt+2؛ أفضل energy-down@t+2 تجاوز null الداخلي للمسارات لكنه لم يضف فوق high-growth baseline، فسُجل مرفوضاً كوسيط إضافي. high-growth→UCDP conflict لم يتجاوز null | مكتملة للاختبارات المتاحة. لا توجد حافة موجبة للاقتصاد→الصراع |
| 6. Formal Path Composer | بُني Composer احتمالي بأوزان fitted من fit فقط. تحسن داخل fit لكنه تدهور في Brier/log-loss خارج العينة مقارنة بالـbaseline، فسُجل مرفوضاً للترقية | مكتملة كاختبار وفشل موثق؛ ليس نموذجاً معتمداً |
| 7. Research Runtime Sandbox | أُنشئ عقد Sandbox ومنفّذ research-only؛ أعاد تشغيل الحالة الاقتصادية المجمدة وأصدر 5,075 alert لـ220 كياناً، دون outcome مستقبلي أو إعادة تدريب أو إرسال خارجي | مكتملة كمسار معزول. ليست production runtime ولا تعديلاً على `market-intelligence-engine` |

## إدماج الملاحظات الجديدة

تم إدماج الكوارث باعتبارها كائناً زمنياً أصلياً يتدرج من حدث إلى صدمة إنتاج ثم تعافٍ، مع إمكان اختبار امتداده إلى التجارة والطاقة فقط بعد عقد محاذاة مستقل يحدد نافذة الحدث، نافذة الصدمة، أفق النتيجة، مطابقة الكيانات، واختبار الـnull. لا يجوز تحويل سجل يومي أو حدثي إلى قيمة سنوية لمجرد إدخاله في لوحة الاقتصاد.

تم إدماج الجوائح كـ`pandemic_health_shock` ذي توقيت يومي أو شهري أصلي، لا كـannual COVID dummy. وتمثل المؤسسات والسياسة كحالات منفصلة تشمل `institutional_transition` و`policy_shock` و`institutional_continuity` و`leader_specific_deviation` عند توفر مشاهدات مؤرخة ومصدرية؛ لا تستخدم أسماء الحزب أو القائد متغيراً سببياً، ولا يُفترض تأثير متوسط ثابت عبر الأنظمة.

## ما لم يثبت

لم يثبت أن الانتباه أو feature importance أو transition score يفسر السببية. لم يثبت أن population أو energy/GDP يضيف عقدة مستقلة إلى النمط الاقتصادي. لم يثبت مسار مباشر من النمو الاقتصادي إلى الصراع في UCDP. ولم يثبت أن Composer الحالي يحسن التنبؤ خارج العينة. السجلات المرفوضة وغير المحسومة محفوظة ولا تدخل بوزن موجب.

## ملف التنفيذ المعزول

يعتمد Sandbox على الحالات المجمدة في:

`experiments/macro_plus_eia_energy/domain_state_v1/DOMAIN_STATES_V1.jsonl`

ويصدر النتائج في:

`experiments/macro_plus_eia_energy/research_runtime_sandbox_v1/`

وتشمل النتائج `RESEARCH_ALERTS_V1.jsonl` و`RESEARCH_ALERTS_V1.csv` و`RESEARCH_RUNTIME_SUMMARY.json` و`RESEARCH_RUNTIME_QA_MANIFEST.json`. كل alert حالة بحثية قابلة للتدقيق وليست توقعاً لنتيجة مستقبلية بحد ذاتها.

## قرار الترقية

لا توجد ترقية إلى production، ولا تعديل في `market-intelligence-engine`. الخطوة التالية الصحيحة بعد هذه الحزمة هي إدخال مصادر حقيقية قابلة للتوثيق للكوارث والجوائح والمؤسسات والسياسة، كل مصدر بعقد تواتره وprovenance الخاص به، ثم اختبار edges داخل كل مجال قبل إعادة فتح Composer. لا يجوز اعتبار وجود العقد أو Sandbox دليلاً على نجاح مسار جديد.
