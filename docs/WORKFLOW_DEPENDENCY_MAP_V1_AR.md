# CHAOS — خريطة اعتماديات GitHub Actions v1

**المستودع:** `uniqueteamyemen/CHAOS`  
**مرجع خط الأساس الذي فُحص:** `main-phase2@e0c13b41ef1bbbdfe46f1dc266a007eb2dedd8d7`  
**فرع Discovery المقارن:** `discovery/d1-domainstate-integrity-v1@f0627eac6fd39a4d26fe128820cf05c58293054d`  
**Discovery integration:** [PR #28](https://github.com/uniqueteamyemen/CHAOS/pull/28) — merged into `main-phase2` at `e0c13b41ef1bbbdfe46f1dc266a007eb2dedd8d7`  
**المنهج:** قراءة ملفات Workflow الفعلية، trigger filters، scripts المستدعاة، artifacts، صلاحيات GitHub Actions، وفحص نتائج التشغيلات عبر GitHub. هذه خريطة اعتماديات تشغيلية ثابتة وليست تقرير نجاح علمي.

## 1. لقطة المستودع

بعد دمج PR #28، تحتوي شجرة `main-phase2` على 1,633 مدخلاً: 1,408 ملفات و225 مجلداً. منها 916 ملفاً تحت `experiments/**`. يحتوي `.github/workflows/` على 27 ملف YAML وملف نصي واحد `b71-trigger-once.txt`؛ الملف النصي ليس Workflow. الرقم السابق 21 YAML كان لقطة ما قبل دمج Discovery.

لا يحتوي `main-phase2` على Workflows لـnpm build أو TypeScript lint أو Python package test عام. تشغيلات Python الحالية إما مرتبطة بفرع Phase 2 المحدد، أو بفروع التجارب التاريخية، أو بأدوات الجرد المتخصصة.

## 2. Workflows الموجودة على main-phase2

### 2.1 مسارات الحوكمة/الضغط المتصلة بفرع Phase 2

| Workflow | المشغّل والنطاق | ما ينفذه فعلياً | المخرجات/الصلاحيات | التقييم |
|---|---|---|---|---|
| `real-data-stress.yml` | Push إلى `main-phase2` عند تغيير `real_data_stress_pipeline/**` (باستثناء النتائج)، أو ملفات Python للكاشف المجمد، أو وثائق المصادر والترخيص وملف workflow؛ ويدعم `workflow_dispatch` | تثبيت متطلبات `real_data_stress_pipeline/requirements.txt`؛ فحص أرشيف التجارب؛ تشغيل اختبارات pipeline؛ تشغيل `python -m real_data_stress_pipeline.run_pipeline` | يقرأ إعدادات `real_data_stress_pipeline/config/**`؛ يجلب بيانات World Bank وUSGS؛ يكتب في `artifacts/real_data_stress/{raw,derived}/`، `real_data_stress_pipeline/results/` والتقرير العربي؛ يرفع artifact ويصدر Releases. `contents: write` ومدة قصوى 360 دقيقة و`cancel-in-progress: true` | Workflow التشغيل الفعلي الحالي لـP2.2. يستورد BreakDetectorV1 المجمد ولا يغير معادلاته. وجود هذا Workflow لا يعني أنه بوابة تمنع تعديل الكاشف |
| `experiments-immutable.yml` | كل Pull Request يستهدف `main-phase2`؛ Push إلى `main-phase2` عند تغيير `experiments/**` أو ملف الحارس أو Workflow أو `AGENTS.md` أو CODEOWNERS | Checkout كامل التاريخ وتشغيل `scripts/guards/check_experiments_immutable.py` على فرق PR أو Push | لا ينشئ artifacts علمية. `contents: read` | يحرس `experiments/**` فقط. لا يفحص `structural_engine/isolated_break_detector_v1/**` |
| `phase1-detector-real-data.yml` | Push إلى `phase1-detector-freeze-phase2-real-data`، أو تشغيل يدوي | اختبارات الكاشف المجمد وفحص بيانات تاريخية حقيقية، ثم توليد تقرير وبصمات | يرفع تقرير الفحص وSHA-256؛ `contents: write` على فرع العمل المحدد | خط Phase 1/real-data تاريخي منفصل، وليس Workflow تشغيل عام على `main-phase2` |

**ملاحظة حدودية:** `real-data-stress.yml` يشمل ملفات الكاشف في trigger paths، لكن ذلك يجعل pipeline يعمل عند تغيرها؛ لا يحظر التغيير. الحارس الوحيد في `experiments-immutable.yml` لا يمرّر مسار الكاشف إلى فحص الفرق. هذه فجوة حماية CI موثقة، وليست إذناً بتعديل الكاشف.

### 2.2 Workflows التجارب والفروع المعزولة

| العائلة | الملفات | الفرع/المسارات التي تراقبها | الأوامر/المخرجات |
|---|---|---|---|
| ERP/A-B-C | `erp-reconcile-tests.yml` | فروع `feat/erp-*` و`review/abc-adversarial`؛ PR paths داخل `experiments/identity_lab/exp_j_erp/**` وملفات Exp M/P/Q/R ذات الصلة | اختبارات reconciliation، Odoo demo/shadow، public-ledger probes، temporal PR/complexity، Exp P/P/Q/R؛ يرفع تقارير تجريبية من `experiments/**` |
| P-engine | `p-engine-parallel-fusion.yml`, `p-engine-asymmetry-guard-cusum.yml`, `p-engine-asymmetry-guard-cusum-confirmation.yml`, `p-engine-mcusum-candidate.yml`, `p-engine-eia-replay.yml`, `p-engine-robust-cusum-calibration.yml`, `p-engine-robust-cusum-holdout.yml`, `p-engine-robustness-holdout.yml` | أساساً `experiment/p-engine-parallel-fusion-v1`; paths كلها تحت `experiments/identity_lab/exp_p_engine*` | اختبارات A/B/C، CUSUM, M-CUSUM، EIA replay، معايرة/holdout، تنزيل artifacts من تشغيل سابق ورفع تقارير نتائج؛ numpy مثبت أو حسب workflow |
| Sequential-break/B-series | `sequential-break-engine.yml`, `sequential-break-engine-audit.yml`, `sequential-break-engine-b3-2-minimal-retest.yml`, `sequential-break-engine-b4.yml`, `sequential-break-engine-b5.yml`, `sequential-break-engine-b6.yml`, `sequential-break-engine-b61.yml`, `sequential-break-engine-b7.yml` | فروع B3/B4/B5/B6/B6.1/B7 و`experiment/sequential-break-engine-v1`، وكلها تستهدف `experiments/identity_lab/**` | اختبارات lifecycle/benchmark/holdout ببذور محددة؛ numpy==2.2.6؛ ترفع تقارير التجارب إلى Actions artifacts |
| Router B7.1 | `b71-isolated-markov-router.yml` | `experiment/b7-1-isolated-markov-router` وملف trigger marker | تثبيت numpy، تشغيل 26M تطوير و27M تحقق، ورفع benchmark report |

هذه المجموعة لها قيمة تاريخية واختبارية، لكنها ليست سلسلة Workflows نشطة لخدمة Engine 1 على `main-phase2`. كما أن تشغيلها يعتمد على كود وبيانات من أرشيف `experiments/**`؛ لذا لا تدمج أو توحّد أو تحذف بناءً على تشابه أسمائها.

### 2.3 القائمة الكاملة لملفات YAML على main-phase2

1. `behavioral-discovery-v1.yml`
2. `b71-isolated-markov-router.yml`
3. `discovery-domain-state-integrity.yml`
4. `erp-reconcile-tests.yml`
5. `experiments-immutable.yml`
6. `p-engine-asymmetry-guard-cusum-confirmation.yml`
7. `p-engine-asymmetry-guard-cusum.yml`
8. `p-engine-eia-replay.yml`
9. `p-engine-mcusum-candidate.yml`
10. `p-engine-parallel-fusion.yml`
11. `p-engine-robust-cusum-calibration.yml`
12. `p-engine-robust-cusum-holdout.yml`
13. `p-engine-robustness-holdout.yml`
14. `phase1-detector-real-data.yml`
15. `real-data-stress.yml`
16. `sequential-break-engine-audit.yml`
17. `sequential-break-engine-b3-2-minimal-retest.yml`
18. `sequential-break-engine-b4.yml`
19. `sequential-break-engine-b5.yml`
20. `sequential-break-engine-b6.yml`
21. `sequential-break-engine-b61.yml`
22. `sequential-break-engine-b7.yml`
23. `sequential-break-engine.yml`
24. `wdi-trade-domainstate-build.yml`
25. `weo-vintage-source-audit-v1.yml`

## 3. Workflows التي أضافها Discovery V1 وأصبحت الآن على main-phase2

| Workflow | Trigger | ما ينفذه | الكتابة/الأثر |
|---|---|---|---|
| `behavioral-discovery-v1.yml` | Push على `discovery/**` مع تغير ملفات Discovery/العقود/مصدر Macro+EIA؛ و`workflow_dispatch`؛ لا يوجد `pull_request` trigger | py_compile، اختبارات discovery، بناء profiles/candidates، Conditional Calendar Null، تحقق hashes/manifest وشروط no-causal/no-forecast | `contents: write`؛ يضيف/يدفع مخرجات `discovery/behavioral_v1/` إلى فرع Discovery ثم يرفع artifact |
| `wdi-trade-domainstate-build.yml` | Push على الفرع المحدد حرفياً `discovery/d1-domainstate-integrity-v1` مع تغير adapter/inputs/tests؛ و`workflow_dispatch`؛ لا يوجد PR trigger | اختبار WDI adapter، بناء DomainStates السنوية، ثم فحص سجل DomainState بأكمله | `contents: write`؛ يكتب `WDI_TRADE_DOMAIN_STATES_ANNUAL_V1.jsonl` وملف run summary ويعمل commit/push إلى نفس الفرع ثم يرفع artifact |
| `weo-vintage-source-audit-v1.yml` | Push على `discovery/**` مع تغير وحدات/عقد WEO؛ و`workflow_dispatch`؛ لا يوجد PR trigger | تثبيت `huggingface_hub` و`pyarrow`، اختبارات WEO، تنزيل mirror/نسخ تاريخية، مقارنة vintage والتحقق من hashes وتصنيف actual/estimate | `contents: write`؛ يحفظ مخرجات مشتقة في `discovery/source_vintage_v1/`، ويرفع الملفات الخام/الدليل كـartifact |
| `observation-foundation-contract.yml` | Pull Request إلى `main-phase2` عند تغيّر Foundation/tests/kernel/contract؛ Push على `main-phase2` وفروع Discovery/فرع GEM | Compile لـidentity/lifecycle/kernel؛ فحص JSON contracts؛ اختبارات deterministic identity/lifecycle | `contents: read`، لا commit ولا write |
| `discovery-domain-state-integrity.yml` | Pull Request إلى `main-phase2` عند تغيّر DomainState registry/campaigns/tests؛ Push على فرع Discovery؛ و`workflow_dispatch` | اختبارات validator ثم قراءة وفحص جميع DomainState assets المسجلة | `contents: read`، يرفع تقرير integrity؛ لا يعدل الأصول |
| `chaos-governance-artifacts.yml` | Pull Request وPush إلى `main-phase2` عند تغيّر governance scripts/kernel/plan؛ و`workflow_dispatch` | بناء D0 inventory عبر kernel، التحقق من manifest، ثم رفع الحزمة | `contents: read`، artifact فقط |

### 3.1 التحقق الدقيق قبل دمج PR #28

PR #28 على الرأس النهائي `f0627eac6fd39a4d26fe128820cf05c58293054d` انتهى بكل 11 check-runs:

| الفحص | الحالة |
|---|---|
| stress | success (PR contract tests only; no long P2.2 run) |
| experiments-immutable | success |
| DomainState Integrity | success as audit execution; asset readiness remains BLOCKED |
| Observation Foundation Contract | success |
| Source Record Identity V1 | success |
| D0 Baseline Artifact Validation | success |
| Behavioral / WDI / WEO `validate-pr` | success (read-only rebuild and validation) |
| Three materialization writer jobs | skipped intentionally on PR events |

لكن هذه checks لا تعوض تشغيل وحدات توليد النتائج الثلاثة على SHA الحالي. آخر التشغيلات الناجحة المتاحة لهذه الوحدات كانت على رؤوس أقدم:

| Workflow | آخر run متحقق | SHA الذي اختُبر فعلاً | علاقته بالرأس الحالي |
|---|---:|---|---|
| WDI DomainState build | 44943154074 | `fbbfe38b15f3bd5cd6f4baa327dd53975c93dded` | أقدم؛ مقارنة ذلك SHA بالرأس الحالي تظهر تغير ملف DomainState JSONL ذي 29,004 سجل |
| Behavioral Discovery V1 | 44946871425 | `a8108a120836cc6384b4d2a745753c8faddfc3ff` | أقدم؛ مخرجات/ملخصات Discovery تغيرت بعده |
| Conditional Calendar Null | 44945139684 | `02fb97e2bbd601219c3547dc2df186da495620c3` | أقدم |
| WEO Source Vintage Audit | 44947329602 | `cbbefa3d25bc109957cfff8f1856f7f6552311bc` | أقدم؛ تغيرت وحدة/ملفات workflow بعده |

كانت هذه التشغيلات السابقة على رؤوس أقدم؛ استبدلتها الآن بوحدات تحقق read-only على PR قبل الدمج. مهام materialization والكتابة بقيت Push/Manual فقط.

## 4. الحماية والصلاحيات

- `main-phase2` محمي على GitHub (branch metadata: `protected=true`).
- `experiments-immutable.yml` هو فحص immutability الوحيد في قائمة Workflows الرئيسية، وهو يفحص `experiments/**` وحده.
- `AGENTS.md` يمنع تعديل كل من `experiments/**` والكاشف المجمد `structural_engine/isolated_break_detector_v1/**`.
- `.github/CODEOWNERS` يوجّه المراجعة للمالك، لكنه لا يفرض بنفسه موافقة أو يمنع الدمج.
- لا يوجد في القائمة فحص CI مكافئ يمنع تعديل مسار الكاشف المجمد.
- ثلاثة Workflows Discovery التي تنتج ملفات مشتقة لها `contents: write`؛ يجب أن تبقى عملياتها على فرع Discovery، لا على فرع محمي أثناء PR validation.
- لا يوجد في Workflows الحالية فحص آلي لـ`npm run build` أو `npm run lint`.

## 5. استنتاج الاعتماديات التشغيلية

1. **المسار الفعلي على main-phase2:** `real_data_stress.yml → real_data_stress_pipeline → frozen BreakDetectorV1`.
2. **مسار Discovery المرشح:** `workflow → scripts/discovery or adapters → discovery_engine / observation_foundation / chaos_governance_kernel → contracts + source data → governed artifacts`.
3. **مسار UI:** لا يتصل مباشرة بمسار Python أو GitHub Actions؛ اعتماده محلي عبر React modules/fixtures داخل `src/`.
4. **التجارب التاريخية:** Workflows الخاصة بها تنفذ ملفات من `experiments/**` وعلى فروع مخصصة، وليست جزءاً من سلسلة تشغيل Engine 1 الحالية.
5. يجب ألا تنتقل ملفات Workflow إلى المسار النشط لمجرد اشتراكها في مكتبة أو مصطلح واحد؛ يلزم وجود dependency edge واضح، وتغطية تشغيل، ومصدر إدخال/مخرج معروف.

## 6. حدود هذا الجرد

تمت قراءة ملفات YAML الـ21 في `main-phase2` وملفات Discovery الستة، وربط أوامرها بالـentrypoints والأصول المعروفة. لم يُفحص محتوى كل GitHub Actions artifact خاماً واحداً واحداً، ولم يُنفذ local checkout أو تشغيل محلي من هذه الجلسة. أي اعتماد غير مذكور هنا يظل بحاجة إلى فحص إضافي، ولا تُزال الملفات أو الفروع اعتماداً على هذا الجرد وحده.
