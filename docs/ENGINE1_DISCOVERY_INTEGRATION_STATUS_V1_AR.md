# CHAOS — Engine 1 Discovery Integration Status

**الحالة:** مدمج كقاعدة Engine 1 مرشحة — لا يعني اعتماد Engine 1 أو السماح ببدء Engine 2.  
**الفرع:** `discovery/d1-domainstate-integrity-v1`  
**PR:** [#28](https://github.com/uniqueteamyemen/CHAOS/pull/28) — merged into `main-phase2` at `e0c13b41ef1bbbdfe46f1dc266a007eb2dedd8d7`  
**رأس المراجعة النهائي قبل الدمج:** `f0627eac6fd39a4d26fe128820cf05c58293054d`  
**رأس main-phase2 بعد الدمج:** `e0c13b41ef1bbbdfe46f1dc266a007eb2dedd8d7`  
**نتيجة الدمج:** 159 commits ضمن PR #28، 0 behind قبل الدمج؛ لا تغيير في `experiments/**` أو الكاشف المجمد.

## 1. تشغيلات إعادة البناء على رأس الكود

ثلاثة Workflows مخصصة أُعيد تشغيلها بعد إضافة تحقق PR read-only وبعد تصحيح تزامن كتابة artifacts:

| المسار | GitHub Actions | النتيجة |
|---|---:|---|
| Behavioral Discovery + Conditional Calendar Null | [44952380422](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44952380422) | success |
| WDI Trade DomainState build | [44952380408](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44952380408) | success |
| WEO 2020 Source Vintage Audit | [44952380583](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44952380583) | success |

هذه تشغيلات Push على رأس الكود `bf4037d5bda841fc07f56d5199a72c7c415c970c`. نتج عنها تحديث artifacts مشتقة إلى فرع العمل قبل الدمج؛ وجرى التحقق من إعادة البناء read-only على رأس PR النهائي. نجاح التشغيل يثبت التنفيذ، لا اعتماداً علمياً.

## 2. Behavioral Discovery V1

الـsummary الحالي يعلن صراحة:

- `status = CANDIDATE_GENERATION_ONLY`
- 1,529 series profiles، 38,225 observations.
- 1,698 candidates: 617 isolated point anomalies، 657 level shifts، 424 slope changes.
- 45 shared-year patterns.
- 697 candidates حساسة لحدود التقسيم وفق مراجعة التقرير.

نتيجة Conditional Calendar Null:

| المقياس | النتيجة |
|---|---:|
| إعادة التوزيع | 10,000 |
| أكبر دعم مرصود | 97 كياناً |
| المئين 95 لأكبر دعم في null | 61 |
| `global_max_conditional_p` | 0.00009999 |
| `null_is_detector_fpr` | false |

النتيجة تشخيص لتركيز توقيت المرشحات بعد تثبيت مجموعة المرشحين. لا تثبت صحة كل مرشح داخل سلسلته، ولا تمثل FPR للكاشف، ولا السببية، ولا التنبؤ. تبقى المخرجات مرشحات غير معتمدة.

## 3. WDI Trade DomainState

ملف تشغيل الـadapter الحالي يثبت:

- 29,004 observed records.
- 259 entities.
- خمسة indicators سنوية للفترة 2000–2024.
- `status = ready_for_domain_state_integrity_and_transition_layer`.
- SHA-256 لمخرج DomainState: `c4f836acc9f57c35f605447def2e0dc412d1363a917b534f0ffde30932729554`.
- لا imputation أو normalization أو source averaging، ولا ادعاء causal، و`edge_evaluation_performed=false`.

هوية المصدر لا تملك `available_at` أو revision/vintage تاريخياً في البيانات التي جرى بناؤها، ولذلك لا يجوز التعامل مع السجلات كما لو كانت point-in-time eligible. كما أن ملخصي max-stat الموجودين في خط الأساس لـWDI within-domain وWDI→economic deterioration سجّلا p=0.4547726137 وp=0.5897051474 (2,000 replicate لكل اختبار)، وكلاهما `research_evidence_only`. جاهزية السجلات لا تعني دعم edge.

## 4. WEO Vintage Audit — القيد الذي بقي قائماً

الحالة المسجلة: `SOURCE_VINTAGE_AUDIT_COMPLETED_WITH_SECONDARY_MIRROR`، مع 139 ISO-3 matched entities. إعادة التشغيل نجحت في قراءة المصدر البديل والتحقق من hashes ورفع artifact.

لكن تنزيل IMF الرسمي لنسختي October 2020 وApril 2021 أعاد HTTP 403. لذلك استخدم التدقيق مرآة طرف ثالث مثبتة على revision:

`econdataverse/imfweo@38f124bb0bf9c07679493c9dc0869dcd53385aee`

هذه المرآة لا تحفظ IMF `Estimates Start After` ولا ملاحظات country/series الأصلية؛ لهذا بقي actual/estimate status مجهولاً لجميع صفوف 2020 المطابقة (139/139) في النسختين. لا يجوز عرض ثبات الاتجاه عبر النسخ وكأنه تحقق من كون القيم actual، أو إثبات لما كان متاحاً وقت الحدث. التقرير يذكر 130/139 دولة ظل فيها اتجاه 2020 دون مرجع الاتجاه عبر النسخ الثلاث، لكنه يصفه اختبار حساسية وصفي وليس إعادة بناء point-in-time.

## 5. بوابات PR على الرأس النهائي

أُضيفت مسارات `pull_request` منفصلة إلى Workflows الثلاثة، مع صلاحية `contents: read` داخل مهام `validate-pr`. مهام توليد/Commit/Push بقيت خاصة بأحداث Push وworkflow_dispatch. التحقق يشتمل على:
- behavioral unit tests + إعادة بناء المرشحات والـnull + manifest validation + مقارنة المخرجات الحتمية، مع استثناء ملفات provenance الزمنية/المتغيرة عن byte-for-byte check.
- WDI adapter tests + إعادة بناء 29,004 DomainStates + registry validator + byte-for-byte check للمخرجات.
- WEO tests + تنزيل النسخ/المرآة المثبتة + SHA verification + تأكيد بقاء actual/estimate unknown حيث metadata غير متاحة.

نجحت جميع بوابات PR على الرأس النهائي `f0627eac6fd39a4d26fe128820cf05c58293054d`: `stress`, `experiments-immutable`, `domain-state-integrity`, `observation-foundation-contract`, `source-record-identity-v1`, `d0-baseline-artifact-validation`, ومهام `validate-pr` الثلاثة لـBehavioral/WDI/WEO. اجتازت كذلك إعادة اختبار تصادم المفتاح الخشن متعدد الأبعاد. بعدها دُمج PR #28 عبر squash في `main-phase2`.

## 6. قرار التسليم

**قرار التكامل:** PR #28 مدمج في `main-phase2` كقاعدة Engine 1 مرشحة؛ الدمج لا يعني اجتياز كل بوابات الجاهزية العلمية.

ما زال Engine 1 غير مجمّد: Pattern discovery, relationship/structural discovery, independent validation, and freeze manifest/handoff gate لم تجتز جميعها بوابة التسليم النهائية. لا يبدأ Engine 2 من هذه النتائج وحدها.

لم تُجرَ أي تغييرات على `experiments/**` أو `structural_engine/isolated_break_detector_v1/**`. كل artifacts المولدة محفوظة في مناطق Discovery/Campaign المخصصة مع hashes وsource provenance؛ لم تُستبدل نتائج تاريخية داخل الأرشيف المجمد.


## 7. DomainState registry — نتيجة التدقيق التفصيلية

تقرير DomainState Integrity من تشغيل [44952544505](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44952544505) أظهر:
- 21 مساراً مسجلاً؛ 15 ملفاً موجوداً و6 مراجع مفقودة.
- 94,231 سجلاً مقروءاً و0 سجلات غير صالحة.
- `readiness = BLOCKED_INCOMPLETE_ASSET_SET`.

نجاح job `domain-state-integrity` يعني أن المدقق نفّذ الاختبارات وقرأ الملفات ولم يجد records غير صالحة. لا يعني أن المجموعة كاملة؛ فالـvalidator مصمم لإرجاع exit code ناجح عند حالة BLOCKED، مع تسجيل readiness الحقيقية داخل report.

المراجع الستة المفقودة:
1. `campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_DOMAIN_STATES_ANNUAL_SOURCE_YEARS_V1.jsonl`
2. `experiments/multi_domain_native_adapters_v1/WHO_COVID_DOMAIN_STATES_DAILY_V1.jsonl.gz`
3. `experiments/multi_domain_native_adapters_v1/imf_imts_v1/domain_state_shards/IMF_IMTS_DOMAIN_STATES_BRA_ANNUAL_V1.jsonl`
4. المسار نفسه مع `CAN`
5. المسار نفسه مع `MEX`
6. المسار نفسه مع `ZAF`

خمسة من المراجع المفقودة داخل `experiments/**`، وهي محمية ولا يجوز إعادة إنشائها أو تعديلها في مسار التنظيف. السادس هو WGI output؛ يوجد WGI source provenance وadapter summary يذكر 32,403 estimates، لكن ملف DomainState المحدد غير موجود في الشجرة، ولا توجد هنا حزمة إعادة تشغيل تثبت إنتاجه.

### تصحيح معنى تصادمات IMF IMTS

كان المدقق يسجل `duplicate_state_slots` من مفتاح خشن يحتوي domain/entity/pattern/timestamp/frequency فقط. هذا المفتاح يتجاهل dimensions حقيقية داخل `source_observations` مثل counterpart country وindicator وtrade flow وvaluation. في 11 shard تاريخياً، سجّل هذا المفتاح 59,553 collision؛ لا يصح وصفها بأنها 59,553 duplicate records.

تم تعديل الكود في هذا الفرع لعرض `coarse_identity_collisions` بدلاً من `duplicate_state_slots`، وتسمية الدالة `domain_state_coarse_key` وإضافة اختبار يثبت بقاء سجلين ذوي أبعاد مصدر مختلفة مع الإبلاغ عن تصادم المفتاح الخشن فقط. لم تُحذف أو تُعدّل أي بيانات تحت `experiments/**`.

التقرير التفصيلي: [DOMAIN_STATE_REGISTRY_AUDIT_V1_AR.md](DOMAIN_STATE_REGISTRY_AUDIT_V1_AR.md).

**قرار ما بعد الدمج:** الكود مدمج باعتباره أساس Engine 1 مرشحاً، مع إبقاء registry completeness بحالة BLOCKED وعدم وصفها بأنها PASS. الدمج لا يصادق على الأصول الستة المفقودة ولا على أي IMF duplicate claim؛ ولا يعني Engine 1 freeze أو السماح بEngine 2.


## 8. حالة المستودع بعد PR #28

أصبحت `discovery_engine/`, `observation_foundation/`, وملفات adapter/governance/workflows الخاصة بها جزءاً من `main-phase2`. يبقى فرع Discovery موجوداً كسجل تاريخي لمراحل البناء والتحقق، وليس خط أساس منفصلاً يلزم cherry-pick منه.

الخطوة التالية في Engine 1 هي إغلاق نواقص DomainState registry دون المساس بمجلد التجارب، ثم استكمال Pattern/Relationship/Structural validation ونسخة freeze manifest مستقلة. لا يبدأ Engine 2 قبل اجتياز عقد التسليم.
