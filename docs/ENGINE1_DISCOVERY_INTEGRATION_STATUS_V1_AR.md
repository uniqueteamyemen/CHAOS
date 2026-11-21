# CHAOS — Engine 1 Discovery Integration Status

**الحالة:** مرشح دمج — لا يعني اعتماد Engine 1 أو السماح ببدء Engine 2.  
**الفرع:** `discovery/d1-domainstate-integrity-v1`  
**PR:** [#28](https://github.com/uniqueteamyemen/CHAOS/pull/28) → `main-phase2`  
**آخر رأس فرع تحقق قبل إضافة هذه الوثيقة:** `5b7193eb8350c28075cb115a34cb8c943bb47709`  
**رأس main-phase2:** `7eb619c1a7756b52aeffb32a06278e786c0dd762`  
**قاعدة الدمج:** `main-phase2`، متزامن بالكامل؛ مقارنة GitHub قبل هذه الوثيقة كانت 150 commits ahead و0 behind.

## 1. تشغيلات إعادة البناء على رأس الكود

ثلاثة Workflows مخصصة أُعيد تشغيلها بعد إضافة تحقق PR read-only وبعد تصحيح تزامن كتابة artifacts:

| المسار | GitHub Actions | النتيجة |
|---|---:|---|
| Behavioral Discovery + Conditional Calendar Null | [44952380422](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44952380422) | success |
| WDI Trade DomainState build | [44952380408](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44952380408) | success |
| WEO 2020 Source Vintage Audit | [44952380583](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44952380583) | success |

هذه تشغيلات Push على رأس الكود `bf4037d5bda841fc07f56d5199a72c7c415c970c`. نتج عنها تحديث artifacts مشتقة إلى الفرع. لا ينبغي الخلط بينها وبين نتائج علمية معتمدة أو مع PR checks التي يجب أن تعمل على رأس المراجعة النهائي.

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

توجد PR checks ناجحة على رأس أقدم قبل آخر materialization commit، لكن GitHub وضع checks التي تبعت commits آلية على حالة `action_required`. أُضيفت هذه الوثيقة بواسطة commit مراجعة عادي لإطلاق مجموعة PR checks جديدة على رأس نهائي واحد. لا يُدمج PR #28 قبل أن تصبح جميع checks المطلوبة على ذلك الرأس `success`، بما فيها `stress` و`experiments-immutable` وValidation Workflows الثلاثة.

## 6. قرار التسليم

**القرار الحالي: PR #28 مرشح للدمج بعد نجاح CI على رأسه النهائي فقط.**

ما زال Engine 1 غير مجمّد: Pattern discovery, relationship/structural discovery, independent validation, and freeze manifest/handoff gate لم تجتز جميعها بوابة التسليم النهائية. لا يبدأ Engine 2 من هذه النتائج وحدها.

لم تُجرَ أي تغييرات على `experiments/**` أو `structural_engine/isolated_break_detector_v1/**`. كل artifacts المولدة محفوظة في مناطق Discovery/Campaign المخصصة مع hashes وsource provenance؛ لم تُستبدل نتائج تاريخية داخل الأرشيف المجمد.
