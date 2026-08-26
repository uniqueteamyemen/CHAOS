# CHAOS — حالة حملة الوكلاء المتوازيين، الجولة الأولى

## القرار التنفيذي

تم تثبيت `CAMPAIGN_BASELINE_V1` باعتباره مرجعاً غير قابل للتعديل، ثم عملت الوكلاء في مساحات مستقلة. المشرف المركزي وحده يقرأ النتائج، يتحقق من schema وprovenance والتواتر وحالة الدليل، ثم يقرر ما إذا كانت النتيجة تدخل الطبقة المشتركة.

## نتيجة المجالات الأولى

| الوكيل | ما توفر فعلياً | ما أُنتج | قرار المشرف |
|---|---|---|---|
| Trade | 125 طلب Comtrade محدوداً لخمسة reporters بين 2000–2024؛ 124 استجابة HTTP 200 واستجابة timeout واحدة، مع تسجيل rate limits السابقة | 124 Trade DomainStates سنوية وTransitionEvidence واحد | `not_testable`: لا توجد بعد تغطية multidimensional reporter×partner×commodity تكفي لاختبار trade disruption |
| Institutions/Policy | WGI 2025 الرسمي، ستة أبعاد، 216 كياناً، سنوات مصدرية 1996–2024 | 32,403 institutional observations و10 حواف داخلية | 5 حواف `rejected` بسبب استمرارية مبتذلة، و5 `not_testable` بسبب ندرة/انحلال target؛ لا policy shock أو leader deviation مستنتج |
| Energy | المخرجات الاقتصادية والطاقية السابقة | إعادة إدراج نتيجة energy-intensity edge السابقة | لا edge جديدة موجبة؛ المسار السابق مرفوض كإضافة |
| Environment/Disaster | USGS event-native، 1,141 حدثاً magnitude≥6.5 | Event DomainStates | `not_testable` حتى تتوفر country attribution وproduction shock وrecovery contract |
| Health/Pandemic | WHO daily، 573,360 صفاً خاماً و215,751 صفاً مبلغاً و239 كياناً | Daily DomainStates | `not_testable` لأي annual GDP edge قبل alignment وproduction-shock contract |

## WGI: ما الذي اختُبر وما الذي لم يُختبر

اختُبرت حافتان داخل كل بُعد من أبعاد WGI الستة: institutional decline persistence وinstitutional continuity persistence، عبر source-observation leads 1 و2 وتقسيم fit/validation/confirmation و2,000 max-stat null. أظهر التشغيل الخام maximum BA=`1.0` وmax-stat `p=1.0`، لكن هذا الحد الأقصى كان ناتجاً عن split شبه خالٍ من حالات decline. لذلك طبقت بوابة دعم قبل الترقية: يلزم وجود 10 حالات موجبة و10 سالبة على الأقل في كل split. بعد البوابة، أُعيد تصنيف حواف decline النادرة إلى `not_testable`، وحواف continuity إلى `rejected_as_trivial_prevalence_persistence` لأن تفوقها على BA التافه لم يتجاوز الحدود المقبولة.

هذه النتيجة لا تقول إن المؤسسات لا تؤثر في الواقع؛ تقول إن **WGI composite وحده، بهذه القواعد وبالتغطية الحالية، لم يثبت edge قابلة للتركيب**. كما أن WGI لا يوفر وحده تاريخ policy shock أو leader-specific deviation، ولذلك بقي هذان المستويان خارج الاستنتاج.

## Trade: القيد الفعلي

الاستخراج المحدود من Comtrade حُفظ كطلبات منفصلة مع URL وHTTP status. استرداد rate-limit لم يُخفَ: الجولة الأولى تضمنت 50 حالة 429، ثم أعاد backoff 49 منها، وبقيت حالة واحدة timeout. الناتج 124 مشاهدة سنوية لإجمالي واردات reporter مع partner عالمي، لكنه ليس شبكة تجارة تاريخية متعددة الأبعاد. لذلك لم تُحسب trade disruption أو recovery، ولم يُسمح للوكيل بتصنيع Edge من فجوة البيانات.

## حالة الطبقة المشتركة

بعد إعادة تشغيل بوابة المشرف:

```text
admitted supported_predictive records = 2
quarantined records = 20
causal claims admitted = 0
```

الحواف المقبولة هي سجلات الدليل الاقتصادي السابقة فقط وفق status `supported_predictive` في سجلها. أما WGI وTrade والحواف الجديدة فبقيت خارج الوزن الإيجابي. الرسم المشترك أصبح `39` عقدة و`44` حافة، منها `2` سجلات evidence مؤهلة و`0` ادعاءات سببية. Pattern Compiler لا يزال ينتج `0` runtime-eligible patterns.

## الاستئناف

كل مجال يملك workspace وrun summary وprovenance أو failure record. الملفات الخام الكبيرة من WGI وComtrade بقيت خارج Git عبر قواعد ignore، بينما العقود والـmanifests والـDomainStates والنتائج وLedger مهيأة للرفع. لا يعتمد الاستئناف على جلسة المتصفح.

القرار التالي هو عدم توسيع Composer. الأولوية البحثية هي إما الحصول على Trade asset تاريخي متعدد الأبعاد بتغطية محددة، أو اختيار مصدر policy مؤرخ ومُعرّف يسمح بفصل policy shock عن WGI، ثم اختبار الحواف داخل المجال قبل أي تركيب عابر للمجالات.
