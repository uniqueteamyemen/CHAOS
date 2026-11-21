# CHAOS — تصنيف مكونات المستودع والفروع v1

**الفرع المرجعي:** `main-phase2@365bb2111c89352466d72e60965246bf238ffabb`  
**فرع جرد الاعتماديات:** `chore/repository-hygiene-audit-v1`  
**تاريخ لقطة GitHub:** 22 نوفمبر 2026  
**قاعدة التصنيف:** وجود كود/بيانات/نجاح Workflow لا يساوي اعتماداً علمياً أو صلاحية تشغيل إنتاجي.

## 1. رموز التصنيف

| الرمز | التعريف | التصرف |
|---|---|---|
| ACTIVE-BASE | جزء من خط الأساس الحالي وله استخدام/أدلة في `main-phase2` | يُحافظ عليه؛ التغيير عبر PR واختبارات |
| CANDIDATE-INTEGRATION | تطوير مرشح في فرع أو PR ولم يندمج | يُراجع ثم يُدمج انتقائياً بعد CI على الرأس الفعلي |
| EVIDENCE-ONLY | بيانات/نتائج بحثية أو readiness؛ لا تكفي لتشغيل engine أو ادعاء العلاقة | تحفظ مع provenance وstatus كما هي |
| MANUAL-TOOLING | أداة تشغيل يدوي تعتمد على ملفات/بيئة خارجية أو لا يغطيها CI | لا تُنقل أو تُحذف قبل جرد استخدام وإعادة إنتاج |
| PRESENTATION-LEGACY | واجهة أو كود محلي/fixtures لا يمثل مصدر الحقيقة العلمي | تبقى للعرض؛ لا ترقيتها إلى runtime علمي |
| FROZEN-ARCHIVE | كود/بيانات/رياضيات تاريخية محمية | ممنوع التعديل/النقل/إعادة التنسيق/الحذف |
| BRANCH-ARCHIVE | فرع تجريبي أو تشخيصي مستقل | حفظ التاريخ؛ لا دمج تلقائي ولا حذف تلقائي |

## 2. تصنيف المجلدات في main-phase2

| المسار | التصنيف | السبب والحكم التنفيذي |
|---|---|---|
| `real_data_stress_pipeline/` | ACTIVE-BASE | نقطة الدخول الحالية لـP2.2 من `real-data-stress.yml`. يستورد الكاشف المجمد ويستخدم إعدادات/اختبارات واضحة. حافظ على فصل نتائج التشغيل والـartifacts الخارجية |
| `chaos_governance_kernel/` | ACTIVE-BASE | وظائف hash/manifests/replay/graph والجودة المستخدمة في مسارات الحوكمة الحالية. لا تنشئ Kernel موازياً |
| `catalog_first/` | ACTIVE-BASE + MANUAL-TOOLING | يحتفظ بجرد المصادر، matrices، readiness reports و27 أداة profiling/readiness. أجزاء كبيرة من raw/staged خارج Git أو مساراتها محلية؛ لا تعتبر كل أداة قابلة لإعادة التشغيل من clone نظيف |
| `campaigns/` | ACTIVE-BASE + EVIDENCE-ONLY | نتائج Agents، DomainStates، انتقالات، Gate artifacts. تُقرأ بحدود قبول صريحة؛ لا تحول كل evidence إلى runtime edge |
| `campaign/` | EVIDENCE-ONLY / LEGACY-ACQUISITION | ملفات acquisition/coverage مبكرة وraw probes. يختلف دورها ومحتواها عن `campaigns/` ولا تعد نسخة مكررة منها |
| `experimental_contracts/` | ACTIVE-BASE + EXPERIMENTAL-SPEC | العقود الحاكمة/التجريبية؛ وجود Contract لا يعني تنفيذ تجربة أو اجتيازها |
| `data/raw/` | EVIDENCE-ONLY | ملفات خام/manifest صغيرة متتبعة؛ لا تمثل كل أصول البيانات المجمعة خارج Git |
| `real_data_stress_pipeline/results/` | EVIDENCE-ONLY | نتائج وmanifests مرجعية للتشغيل التاريخي؛ لا تعاد كتابتها بغرض التنظيف |
| `src/` | PRESENTATION-LEGACY | React/Vite على fixtures وحسابات محلية. لا يوجد اتصال مباشر بمحرك Python أو workflow artifacts في شجرة imports التي تتبعت |
| `scripts/*.ts` | PRESENTATION-LEGACY / MANUAL | أدوات يدوية تستورد بيانات ووحدات من `src/`; غير مشمولة في `tsconfig.json` ولا يغطيها CI |
| `catalog_first/tooling/` | MANUAL-TOOLING | 27 سكربت Python؛ متطلبات غير مقفلة، وبعض مداخلها/مخرجاتها raw/staged خارج Git ومسارات workspace مطلقة |
| `tooling/` | MANUAL-TOOLING | سكربتا Shell لجلب/استئناف Comtrade bounded acquisition؛ يكتبان إلى `campaigns/agents/trade_v1/raw/` المستثنى من Git |
| `lightning_logs/` | EVIDENCE-ONLY / HISTORICAL | 15 ملف hparams سجل تشغيل تاريخي؛ لا تحذفها بسبب عدم وجود entrypoint حالي |
| `.github/workflows/` | MIXED | Workflows P2.2، حراس، Phase 1، ومسارات B-series/P-engine/ERP قديمة. لا دمج/حذف بناء على الأسماء |
| `structural_engine/isolated_break_detector_v1/` | FROZEN-ARCHIVE | الكاشف المعتمد كأرشيف Phase 1؛ أي تعديل رياضي أو تنظيمي ممنوع في هذه المهمة |
| `experiments/**` | FROZEN-ARCHIVE | 916 ملفاً في main-phase2؛ سجل تاريخي ومخرجات مثبتة. لا تعديل، نقل، rename، reformat، أو حذف |

## 3. تصنيف Discovery V1

**الفرع:** `discovery/d1-domainstate-integrity-v1`  
**PR:** [#28](https://github.com/uniqueteamyemen/CHAOS/pull/28) — Draft، open  
**الرأس:** `1c0ea804b4a3112ee553ee2e63b7a4a15fab50a6`  
**العلاقة الحالية بـmain-phase2:** 140 commits ahead و1 behind؛ فرق التأخر هو توثيق main-phase2 الذي أُضيف بعد تفرع Discovery. يجب تسوية هذا الفرق قبل الدمج.

| المكون في Discovery branch | التصنيف | القرار |
|---|---|---|
| `observation_foundation/` | CANDIDATE-INTEGRATION | مصدر الهوية/versioning وlifecycle؛ يُحافظ عليه ويُراجع التداخل مع kernel والعقود |
| `discovery_engine/` | CANDIDATE-INTEGRATION | Behavioral discovery وcalendar null وWEO vintage audit |
| `chaos_governance_kernel/domain_state.py` | CANDIDATE-INTEGRATION | امتداد للـkernel الحالي لا بديل عنه |
| `scripts/adapters/build_wdi_trade_domain_states.py` | CANDIDATE-INTEGRATION | بناء DomainState سنوي من WDI source records |
| `scripts/discovery/**` | CANDIDATE-INTEGRATION | نقاط تشغيل discovery/null/vintage |
| `scripts/governance/**` | CANDIDATE-INTEGRATION | D0 inventory وDomainState registry validation |
| `discovery/**` | EVIDENCE-ONLY | candidate profiles/results/manifests؛ نتائجها ليست validated patterns أو forecasts |
| `campaigns/agents/trade_v1/WDI_TRADE_DOMAIN_STATES_ANNUAL_V1.jsonl` | EVIDENCE-ONLY / DERIVED | 29,004 DomainState records في مخرج V2 مشتق؛ لا يخلط مع source observations أو مع evidence الخاص بوجود edge |
| Workflows الستة الجديدة | CANDIDATE-INTEGRATION | ثلاثة workflows توليدية لها contents:write ولا تعمل على PR events؛ يلزم توفير مسار PR read-only للتحقق الدقيق من الرأس |

### نتائج Discovery لا تُرقّى تلقائياً

- تقرير Behavioral Discovery يصف نفسه `CANDIDATE_GENERATION_ONLY`, و`forecasting_performed=false`, و`causal_claims_permitted=false`.
- 1,529 سلسلة و38,225 ملاحظة و1,698 مرشحاً و45 shared patterns هي مخرجات المرشحات وفق artifacts الفرع؛ 697 مرشحاً حساس للتقسيم.
- WDI Adapter status هو `ready_for_within_domain_edge_contract`. لكن نتائج الاختبار المسجلة في main-phase2 للـWDI within-domain max-stat تعطي `p=0.4547726137` (2,000 replicate)، ونتائج WDI-to-economic deterioration تعطي `p=0.5897051474` (2,000 replicate). كلاهما `research_evidence_only`، ولا يسمح بادعاء causal.
- Conditional Calendar Null وWEO vintage runs الناجحة كانت على SHAs أقدم من رأس PR #28. أربع PR checks على رأس PR ناجحة (Governed Artifacts, Observation Foundation Contract, DomainState Integrity, experiments-immutable)، لكن WDI/Behavioral/WEO materialization لم يُتحقق منها على الرأس الحالي.
- بوابة Supervisor على main-phase2 تسجل pass، لكن `compiled_runtime_eligible=0` و`causal_claims=0`. نجاح البوابة ليس تصريح تشغيل.

**قرار Stage B:** Discovery V1 هو المرشح التالي للدمج في Engine 1، لكن لا يزال CANDIDATE-INTEGRATION، لا Active. يُمنع دمجه حتى يُستكمل التحقق على exact PR head وتحديث PR من أثر commit الوثائقي على main-phase2.

## 4. تصنيف المسارات السيزمية/USGS

### 4.1 فروع P2.2.3 المتفرعة

| الفرع | المقارنة مع main-phase2 | أحدث رأس معروف | آخر تشغيل موثق على الرأس | التصنيف |
|---|---:|---|---|---|
| `fix/p2-2-3-usgs-catalog-integrity-v1` | 87 ahead / 1 behind؛ 28 ملفاً | `12c3ce747078936dc5eb789fceb23799f3d91fe6` | Run 44936295839 success، على الرأس نفسه | CANDIDATE-INTEGRATION منفصل، يحتاج انتقاء |
| `feat/p2-2-3-magnitude-type-provenance-v1` | 97 ahead / 1 behind؛ 28 ملفاً | `1188882ab76fac78133a5926e25f6a032e519b42` | Run 44935268368 success؛ job الثاني skipped | CANDIDATE-INTEGRATION جزئي |
| `fix/p2-2-3-gem-snapshot` | 73 ahead / 1 behind؛ 27 ملفاً | `995487aa394d1b3bee77c1b62db55b7fd75329cd` | Run 44791078808 success، jobان | CANDIDATE-INTEGRATION جزئي/أقدم lineage |

هذه الفروع ليست ثلاثة نسخ متطابقة. مقارنة USGS base إلى Magnitude branch تظهر Magnitude متقدماً 14 ومتأخراً 4 commits عن USGS، مع اختلافات في Workflow audit و`run_pipeline.py` وaudit script/tests. مقارنة USGS إلى GEM snapshot تظهر GEM متقدماً commit واحداً ومتأخراً 15. لا يدمج أي منها بكامل الفرع.

### 4.2 ما الذي أثبته USGS run وما لم يثبته

Run [44936295839](https://github.com/uniqueteamyemen/CHAOS/actions/runs/44936295839) على الرأس `12c3ce7...` نجح في وظيفتين:
- 23 اختباراً للمساعدات، منها spatial/magnitude/time validation، quarantine/accounting، حفظ magnitude metadata، snapshot checks وsource gate.
- تدقيق Domain Null/Declustering على خمسة أحزمة، وأظهر `source_gate=True`، ورفع artifact يحوي 43 ملفاً بحجم 21,356,722 byte.

لكن وثيقة `P2_2_3_MAGNITUDE_COMPLETENESS_READINESS_V1_AR.md` تصرّح بعدم وجود مقدر Mc معتمد. لا توجد مقارنة مكتملة مع Zaliapin–Ben-Zion، ولا ETAS/point-process model fit معتمد. Poisson الموجود موسوم benchmark only. لذلك تصنيف النتيجة: نجاح integrity pipeline واختبارات تنفيذية، وليس اعتماد seismic null أو completeness أو earthquake prediction.

## 5. تصنيف فروع Markov/diagnostics

| الفرع/PR | الوضع المقارن والهدف | التصنيف |
|---|---|---|
| `p2.2.2-markov-calibration-audit` | 7 commits ahead/1 behind؛ حزمة diagnostics | BRANCH-ARCHIVE / DIAGNOSTIC |
| `fix/p2-2-2-rho-observability-v1` | 17 ahead/1 behind؛ PR #24 يستهدف فرع calibration وليس main-phase2 | CANDIDATE-DIAGNOSTIC |
| `fix/p2-2-3-rho-observability-v1` | 34 ahead/1 behind؛ 10 ملفات audit وworkflows/tests | DIAGNOSTIC |
| `fix/p2-2-4-rho-power-observability-v1` | 28 ahead/1 behind؛ power audit امتداد منفصل | DIAGNOSTIC |
| `diag/markov-real-data-behavior` | 21 ahead/1 behind؛ آخر تشغيلين 44935931443 و44935937210 ناجحان على SHAs التشغيل نفسها | DIAGNOSTIC |
| `diag/domain-null-and-declustering` | 23 ahead/1 behind؛ audit زلزالي مستقل | DIAGNOSTIC |
| `p2.2.2-seismic-null-contract` | 5 ahead/1 behind؛ عقد تصميم واختبارات | EVIDENCE-ONLY / DESIGN CONTRACT |

لا تتضمن هذه التصنيفات إذناً بتغيير الكاشف المجمد أو إدخال Markov إلى Discovery. الهدف هو حفظ diagnostics منفصلة عن التنفيذ العلمي النشط.

## 6. تصنيف الفروع التاريخية

| عائلة الفروع | التصنيف | المعالجة |
|---|---|---|
| `experiment/b3-*`, `experiment/b4-*`, `experiment/b5-*`, `experiment/b6-*`, `experiment/b7-*` | BRANCH-ARCHIVE | حفظ سلسلة البحث/المقارنات القديمة؛ لا دمج إلى Engine 1 |
| `experiment/p-engine-parallel-fusion-v*`, `experiment/gemini-p-engine-method-v1`, `experiment/deepseek-method-on-our-matcher`, `experiment/paylock-identity-blind-v1` | BRANCH-ARCHIVE | مسارات بحث متخصصة؛ لا تدمج لمجرد احتوائها على domain-neutral logic |
| `feat/domain-neutral-observation-kernel-v1`, `feat/domain-neutral-residual-contract-v1` | BRANCH-ARCHIVE / REFERENCE | مصدر تاريخي لمراجعة العقود والأفكار؛ المقارنات مع main تبين divergence كبيراً، فلا تدمج wholesale |
| `erp-*`, `feat/erp-*`, `benchmark/erp-*`, `review/abc-adversarial` | BRANCH-ARCHIVE / SEPARATE PROJECT | مسار ERP مستقل عن Engine 1. PRs #2/#4/#9/#20/#3 أغلقت من طابور الدمج النشط دون حذف الفروع أو الملفات |
| `archive/phase1-detector-freeze-v1.0`, `phase1-detector-freeze-phase2-real-data` | FROZEN-ARCHIVE | أرشيف Phase 1 ومرجعه، يحفظ دون تعديل |
| `fix/p2-2-non-cancelling-concurrency` | SMALL-FIX-CANDIDATE | تعديل Workflow صغير فقط؛ لا يدمج قبل تحليل التشغيلات/الأثر |
| `fix/50k-peer-benchmark-unit-gate-v1` | BRANCH-ARCHIVE | 3 commits ahead لكنه 197 behind عن main-phase2 ويعدل `experiments/**`; ليس مسار دمج |

**مبدأ حفظ التاريخ:** إغلاق PR لا يعني حذف الفرع أو commit، وتصنيف branch كأرشيف لا يغير محتواه. لا تستخدم branch deletion أو directory deletion كآلية تنظيف في هذه المرحلة.

## 7. تصنيف جاهزية المصادر — مع الفصل بين وجود البيانات ودليل العلاقة

| المصدر | ما أثبتته الملفات/التقارير الحالية | حالة الاستخدام |
|---|---|---|
| Macro + EIA Energy | لوحة 139 كياناً × 25 سنة (2000–2024) و11 متغيراً؛ توجد provenance وgap profiles | مصدر بيانات متاح لـDiscovery behavioral؛ اختبار Energy-intensity → deterioration في سجل agent رُفض كإضافة positive edge (`null_p=0.3013493253`) |
| WDI Trade | 29,004 observed records، 259 كياناً، 5 indicators، annual 2000–2024 | بيانات WDI موجودة في main؛ adapter V2/DomainState JSONL مخرجات فرع Discovery. نتائج max-stat الحالية (p=.4548 within-domain، p=.5897 cross-domain) لا تدعم edge إيجابياً |
| UN Comtrade | Bounded preview واحد بصف واحد + world aggregate probe؛ acquisition الأوسع 124 records/5 reporters/2000–2024 مع فشل request واحد، لكنها لا تغطي partner/commodity/flow بالشكل اللازم لكل network | لا تزال غير كافية لربط تاريخي country-partner-commodity؛ `TRADE_AGENT_READINESS_V1` يقرر not_testable |
| IMF IMTS | استعلام 15 reporter نجح لـXG/MG؛ acquisition لـ139 reporter مع XG فقط سجّل 139 استجابة 200؛ acquisition المزدوج XG+MG لـ139 reporter سجل 139 استجابة 403 | جزئي ومفيد لمسار export-only، لكن واردات/تغطية مؤشرات مزدوجة لجميع 139 غير مكتملة؛ لا تختزل الحالة إلى “4 ملفات ناقصة” أو “IMF جاهز” |
| USGS M6.5+ | 1,141 حدثاً native event؛ integrity/de-dup/spatial/time checks في فرع USGS نجحت | الحدث موجود؛ cross-domain path blocked لغياب country attribution/production shock/recovery. لا annual alignment بلا contract |
| WHO COVID | 573,360 صف خام يومي موثق، و215,751 reported rows مستخدمة في states، 239 entities | لا يصح مسار إلى GDP annual حالياً؛ blockers تشمل reporting date semantics، اختلاف البلدان، retrospective revisions، وعدم وجود production-shock observation |
| WGI | 1,296 indicator rows، 216 entities، 32,403 estimate DomainStates؛ policy shock states=0 وleader-specific deviations=0 | institutional measurement only؛ continuity edges رُفضت كـtrivial prevalence، والـdecline edges not_testable؛ positive composer edges=0 |
| UCDP GED | Raw GED ZIP موصوف في manifest (39,122,522 bytes) خارج Git، وموسوم `used_in_current_replication=false`؛ Country-Year profile 7,132 صفاً/74 عموداً/1989–2025 موجود في readiness tooling | لا تخلط GED daily مع Country-Year native source. لا يمكن إعادة بناء الخام من Git دون external source asset؛ الحالة ليست “لا توجد بيانات UCDP” |
| NOAA GHCN-Daily | profile/selection لعدد 9 محطات؛ توثيق تغطية وmetadata، ومسارات CSV في workspace محلي خارج Git | readiness metadata موجودة؛ بيانات المحطات الخام لا تُعامل كجزء reproducible من clone Git الحالي |

## 8. بوابات القبول المرتبطة بالتصنيف

- مصدر البيانات موجود ≠ adapter validated.
- Adapter validated ≠ edge supported.
- Edge supported ≠ causal relationship.
- Supervisor gate pass ≠ runtime eligible.
- Behavioral candidate ≠ validated pattern.
- Detector confirmation ≠ external structural truth.
- Null simulation ≠ FPR ما لم يطابق آلية البيانات ويجتز تشخيص الملاءمة.
- Workflow success ≠ صحة علمية؛ هو دليل على نجاح ما نفذه ذلك التشغيل على SHA محدد.

## 9. قرار Stage B

1. نعتمد `main-phase2` كمرجع دمج وحيد.
2. Discovery V1 يبقى CANDIDATE-INTEGRATION، وهو ترتيب الدمج الأول بعد تحديث PR/CI.
3. USGS catalog-integrity يبقى مرشح PR مستقل بعد Discovery، ويُنتقى منه فقط إصلاح source integrity/magnitude provenance الفريد مع حفظ حدود علم Mc وnull.
4. Markov/ERP/P-engine/B-series تبقى مسارات تشخيص/أرشيف منفصلة؛ لا تدخل تنظيف Engine 1.
5. `src/` و`catalog_first/tooling/` لا تُحذف. تُؤجل قرارات orphan/duplicate إلى dependency/reference hash audit.
6. لا نقل أو حذف أو إعادة تسمية ملفات في Stage B؛ هذه المرحلة تصنيف لا عملية نقل.
