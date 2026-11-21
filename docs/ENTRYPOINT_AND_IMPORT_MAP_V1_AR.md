# CHAOS — خريطة نقاط الدخول والاعتماديات البرمجية v1

**المستودع:** `uniqueteamyemen/CHAOS`  
**الفرع المرجعي للكود الأساسي:** `main-phase2@365bb2111c89352466d72e60965246bf238ffabb`  
**الفرع المرجعي لمحرك Discovery المرشح:** `discovery/d1-domainstate-integrity-v1@1c0ea804b4a3112ee553ee2e63b7a4a15fab50a6`  
**الغرض:** تحديد نقطة الدخول، الاعتماديات، حدود البيانات، ومواقع الكتابة قبل أي إعادة تنظيم مادي.

## 1. حقيقة التشغيل: مستويان منفصلان

### 1.1 Python — مسار الحساب والبحث المرجعي

العمل العلمي/التشغيلي في خط الأساس مبني على Python. وحدات الكاشف واختبارات البيانات والـworkflows تتبع هذا المسار. لا يوجد في الكود الذي فُحص ربط تنفيذي من React إلى وحدات Python أو إلى API خلفي يقدّم نتائج الكاشف.

### 1.2 TypeScript/React — Presentation وfixtures تجريبية

الجذر يحتوي تطبيق Vite/React. وحدات `src/utils/**` تنفذ بعض حسابات العرض محلياً على بيانات fixtures؛ لا تشغّل Python ولا تستورد مخرجات تشغيل GitHub Actions بطريقة ديناميكية. لذلك لا تُعد هذه الوحدات محرك Discovery العلمي المعتمد، حتى عندما تحمل أسماء مثل Discovery أو Forecast.

**القرار المعماري المستخلص من الاعتماديات:** لا نحذف الواجهة العاملة ولا نعيد بناءها الآن؛ نثبت فقط أنها طبقة عرض/تجربة منفصلة عن مصدر الحقيقة العلمي.

## 2. Python: نقاط الدخول والاعتماديات

### 2.1 خط الضغط التاريخي P2.2

`python -m real_data_stress_pipeline.run_pipeline`

| العنصر | الاعتماد |
|---|---|
| نقطة الدخول | `real_data_stress_pipeline/run_pipeline.py` |
| ملفات الإعداد | `real_data_stress_pipeline/config/pipeline.json`, `gem_indicators.json`, `seismic_belts.json` |
| المتطلبات المعلنة | `real_data_stress_pipeline/requirements.txt`: `numpy>=1.26,<3`, `openpyxl>=3.1,<4`, `statsmodels==0.15.0` |
| الكاشف المستورد | `structural_engine.isolated_break_detector_v1.BreakDetectorV1` و`DEFAULT_MARKOV_THRESHOLD` |
| مصدر البيانات | World Bank Pink Sheet (في الذاكرة)، World Bank GEM، USGS ComCat؛ مع source snapshots وquery parameters وبصمات |
| أماكن الكتابة | `artifacts/real_data_stress/raw/`, `artifacts/real_data_stress/derived/`, `real_data_stress_pipeline/results/`, `REAL_DATA_STRESS_REPORT_AR.md` |
| الاختبارات | `real_data_stress_pipeline/tests/test_pipeline.py` |
| Workflow | `.github/workflows/real-data-stress.yml` |

المسار يستورد الكاشف المجمد. هذا اعتماد قراءة/استخدام؛ لا يبرر تعديل الكاشف أو تغيير ثوابته في تنظيف المستودع.

#### وحدة SourceFetcher المنفصلة

`real_data_stress_pipeline/fetch.py` تعرّف `SourceFetcher` باستخدام `requests` و`urllib3`، وتكتب snapshots وmanifest metadata. لكن `requests` غير موجود في `real_data_stress_pipeline/requirements.txt`، و`run_pipeline.py` لا يستورد هذه الوحدة في النسخة التي فُحصت، ولا تستدعيها Workflow الحالية. هذا يعني أنها **وحدة غير متصلة بنقطة دخول P2.2 الحالية**، وليس دليلاً كافياً وحده على أنها مكررة أو غير مستخدمة خارج المسار الذي فُحص. لا تحذف قبل global reference audit/قرار مستقل.

### 2.2 Governance Kernel في main-phase2

| الملف | الوظيفة/الاعتماد |
|---|---|
| `chaos_governance_kernel/core.py` | SHA-256، canonical object hash، manifests، artifact validation، replay، evidence graph، JSON/JSONL writes |
| `chaos_governance_kernel/checks.py` | فحوص CSV وجودة المدخلات |
| `chaos_governance_kernel/cli.py` | CLI فرعي: `validate`, `replay`, `graph`, `data-audit`, `record` |
| `chaos_governance_kernel/__init__.py` | تعريف الحزمة |

هذه المكتبة تعتمد على Python standard library في النسخة الأساسية التي فُحصت. لا يوجد `pyproject.toml` أو `setup.py` أو تثبيت package مركزي؛ الاستدعاء الحالي يتم من داخل repository root، غالباً عبر `python -m` أو imports محلية.

في فرع Discovery أضيف `chaos_governance_kernel/domain_state.py` لفحص DomainState assets. وهو ليس موجوداً في `main-phase2` قبل دمج PR #28.

### 2.3 Catalog First — أدوات الاستكشاف والجرد

يوجد 27 برنامج Python تحت `catalog_first/tooling/`:

- Acquisition/inventory/reporting: `build_acquisition_inventory.py`, `build_acquisition_report.py`, `extract_catalog_metadata.py`.
- Readiness/matrix generation: `build_data_readiness_gate.py`, `build_data_readiness_report.py`, `build_gap_augmented_readiness.py`, `build_macro_plus_eia_raw_and_gap_analysis.py`, `assess_matrix_candidates.py`, `select_first_matrix_candidates.py`, `audit_entity_intersection.py`.
- Data profiling: `profile_bulk_datasets.py`, `profile_eia_jsonl.py`, `profile_fred_eia.py`, `profile_gap_assets.py`, `profile_gsom_monthly.py`, `profile_noaa_station_files.py`, `profile_ucdp.py`, `profile_ucdp_country_year.py`, `profile_workbooks_detailed.py`, `inspect_weo_indicators.py`.
- Selection/QA: `select_eia_annual_series.py`, `select_noaa_stations.py`, `check_weo_candidate_ids.py`, `summarize_coverage_gate.py`, `qa_data_readiness_gate.py`, `qa_gap_augmented_readiness.py`.
- Visualization: `plot_readiness_summary.py`.

**الاعتماديات المرصودة:** عدة أدوات تستورد `pandas`؛ أداة الرسم تستورد `matplotlib` و`numpy`. لا يوجد ملف متطلبات مستقل لهذه المجموعة ولا Workflow في GitHub يثبت تنفيذها بشكل موحد. بعضها يشير إلى `catalog_first/raw/` و`catalog_first/staged/`، وهي مسارات يستثنيها `.gitignore` أو تعتمد على ملفات محلية غير موجودة ضمن شجرة Git المتتبعة. وبعض السكربتات تتضمن مسارات workspace مطلقة مثل `/home/ubuntu/market_intelligence_workspace/`.

**التصنيف التشغيلي:** أدوات جرد وإعادة بناء readiness، وليست engine runtime أو خدمة استشعار. إعادة التشغيل من clone نظيف ليست مضمونة حتى تكتمل أصول المصادر الخارجية ومواصفات البيئة.

### 2.4 Structural Engine المجمد

المسارات الموجودة:

- `structural_engine/isolated_break_detector_v1/__init__.py`
- `break_detector_v1.py`
- `engine_fast_ref.py`
- `engine_markov_cusum.py`
- `run_real_data.py`
- `tests/test_contract.py`
- `tests/test_real_data_adapter.py`

يعتمد التنفيذ على `numpy`. تستورد `break_detector_v1.py` محركي Fast وMarkov؛ وتستورد pipeline P2 واجهة `BreakDetectorV1`. هذه منطقة frozen بالكامل في هذا المسار؛ أُدرجت الاعتماديات لرسم الخريطة فقط، لا لتبرير إعادة التنظيم داخلها.

### 2.5 الحارس الحالي

`scripts/guards/check_experiments_immutable.py` هو نقطة دخول حارس CI. يستخدم `git diff --name-status` ويحدد نطاقه صراحة بـ`-- experiments/`. لا يتضمن مسار `structural_engine/isolated_break_detector_v1/`، ولذلك لا يحرس ذلك المسار حالياً.

## 3. Discovery V1: خريطة الفرع المرشح

هذه الوحدات موجودة في `discovery/d1-domainstate-integrity-v1`، ولم تكن مدمجة في `main-phase2` عند كتابة هذه الخريطة.

### 3.1 Source Observation وLifecycle

| الملف | الوظيفة والاعتماديات |
|---|---|
| `observation_foundation/record_identity_v1.py` | هوية سجل المصدر/نسخة السجل، canonical normalization وhashing؛ يعتمد على standard library |
| `observation_foundation/lifecycle_v1.py` | دورة حياة الفرضيات وحالات مدخلات الأدلة؛ يستدعي kernel الحالي، ويشير إلى Research Ledger والعقود |
| `observation_foundation/contracts/**` | JSON schemas لهوية الملاحظة، lifecycle، input disposition |
| `experimental_contracts/RESEARCH_LEDGER_CONTRACT_V1.json` | عقد سجل الأبحاث المستخدم من lifecycle |
| `experimental_contracts/TEMPORAL_ALIGNMENT_CONTRACT_V1.json` | عقد التوافق الزمني |
| `tests/observation_foundation/**` | اختبارات deterministic identity/lifecycle |

### 3.2 DomainState

| الملف | الوظيفة |
|---|---|
| `chaos_governance_kernel/domain_state.py` | قراءة والتحقق من DomainState JSONL/JSONL.GZ، schema، hashes ومراجع الأصل |
| `scripts/governance/validate_domain_state_registry.py` | فحص الأصول المسجلة، دون تعديل الأصول |
| `scripts/governance/build_d0_inventory.py` | بناء D0 inventory/manifest والتحقق عبر kernel |
| `tests/governance/test_domain_state_integrity.py` | اختبارات validator |

### 3.3 WDI Trade adapter

`scripts/adapters/build_wdi_trade_domain_states.py`:

`WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv` + `WDI_TRADE_SELECTED_SERIES_METADATA.csv` + `WDI_TRADE_EXTRACT_SUMMARY.json`  
→ adapter (يستورد `record_identity_v1` وkernel hash/manifest functions)  
→ `WDI_TRADE_DOMAIN_STATES_ANNUAL_V1.jsonl` + `WDI_TRADE_DOMAIN_ADAPTER_RUN_V2.json`  
→ `validate_domain_state_registry.py`  
→ upload artifact وcommit/push بواسطة Workflow WDI.

ملف النتائج يحتوي 29,004 سجل، 259 كياناً، خمس مؤشرات، وتواتر سنوي 2000–2024 وفق summary الخاص بالفرع. هذه جاهزية لإجراء within-domain edge contract، وليست إثبات edge إيجابي أو سببية.

### 3.4 Behavioral Discovery وCalendar Null

- `discovery_engine/behavioral_discovery_v1.py` يستورد `chaos_governance_kernel.core` و`observation_foundation.record_identity_v1`، ويعالج Macro+EIA panel مع provenance/summary/contract.
- `scripts/discovery/run_behavioral_discovery_v1.py` يحدد مسارات الإدخال والعقد ويستدعي engine.
- مخرجاته تحت `discovery/behavioral_v1/`: profiles، candidates، shared year patterns، summary، manifest وvalidation.
- `discovery_engine/calendar_coincidence_null_v1.py` يستهلك candidates والعقد، ويستخدم randomization/redistribution مع حفظ شروطه وبياناته الوصفية؛ `scripts/discovery/run_calendar_coincidence_null_v1.py` نقطة الدخول.
- الاختبارات: `tests/discovery/test_behavioral_discovery_v1.py` و`test_calendar_coincidence_null_v1.py`.

الملخص المسجل يصف المخرجات بأنها `CANDIDATE_GENERATION_ONLY`، ويمنع causal claims وforecasting. لذلك لا ترقّى هذه النتائج إلى Patterns validated أو تنبؤات.

### 3.5 WEO vintage audit

- `discovery_engine/weo_vintage_audit_v1.py` يستورد kernel ووحدة mirror.
- `discovery_engine/weo_hf_mirror_v1.py` يستورد `huggingface_hub` و`pyarrow.dataset` بالإضافة إلى standard library.
- Workflow يثبت `huggingface_hub` و`pyarrow` مباشرة، ولا يوجد ملف متطلبات منفصل مقفل أو lockfile Python لهذه الوحدة.
- نقطة الدخول: `scripts/discovery/run_weo_vintage_audit_v1.py`.
- مخرجات: `discovery/source_vintage_v1/` (audit JSON، comparison CSV، vintage manifest) مع raw evidence في Actions artifact.

تقرير المراجعة نفسه ينص أن actual/estimate classification لم يكتمل بالكامل؛ لذلك sign stability ليست مصادقة كافية على حقيقة التقدير أو صلاحية النموذج.

## 4. TypeScript/React: شجرة الاستيراد

### 4.1 تكوين التطبيق

- `package.json`: React 18، React DOM، Vite 6، TypeScript 5.7، Tailwind Vite، Recharts، Motion، Lucide، clsx وtailwind-merge.
- Scripts: `dev`, `build`, `lint`, `preview`.
- `lint` يشغّل `tsc --noEmit`.
- `tsconfig.json` strict، ويشمل `src` فقط؛ لا يشمل `scripts/*.ts`.
- لا يوجد npm/TS CI Workflow في `.github/workflows/` الحالي، ولم يظهر package lock في الشجرة المفحوصة.
- `src/main.tsx → src/App.tsx → components`.

### 4.2 مسارات المكونات

| المكون | الوحدات المحلية التي يستوردها | مصدر البيانات |
|---|---|---|
| `HumanFleetEngineView` | `humanImpactCalculus`, `fleet50Series` | fixture ثابت |
| `PatternDiscoveryEngineView` | `patternDiscoveryEngine`, `patternEvidenceReport` | `fleet50Series` ووظائف الحساب المحلي |
| `FutureForecastEngineView` | `futureForecastEngine` | `fleet50Series`, `humanImpactCalculus` |
| `TransitionRobustnessView` | `transitionEngine` | `fleet50Series`, `transition2013Data`, `humanImpactCalculus` |
| `ChaosRuntimeView` | `chaosRuntimeV1`, `types` | بيانات runtime محلية مدخلة/معروضة في الواجهة |
| `DiscoveryEngineView` | `discoveryEngineCore`, `timeSeriesLibrary`, `types` | fixture محلي من مكتبة السلاسل |
| `SupervisorGateView` | `causalCircuitBreaker`, `chaosData`, `timeSeriesLibrary` | fixtures وعقود ثابتة |
| `ContractsView` | `chaosData` | تعريفات عقود معروضة داخل TypeScript |
| `DataCatalogView` | `chaosData` | readiness metrics ثابتة |
| `GovernanceKernelView` | `governanceKernel`, `chaosData` | حسابات/بيانات محلية للعرض |
| `ModelBenchmarksView`, `GuardrailsView`, `Header` | React/Lucide أساساً | Presentation |

### 4.3 وحدات البيانات الثابتة

- `src/data/chaosData.ts`: عقود، بيانات readiness، ونصوص evidence/path metadata؛ يحتوي أسماء مسارات legacy لملفات تحت `experiments/**`. وجود المسار النصي ليس دليلاً على أن React يقرأ الملف من القرص.
- `src/data/fleet50Series.ts`: مجموعة بيانات مضمّنة كبيرة.
- `src/data/timeSeriesLibrary.ts`: مكتبة سلاسل مضمّنة.
- `src/data/transition2013Data.ts`: بيانات انتقال مضمّنة.
- `src/types.ts`: واجهات/أنواع مشتركة للـUI.

### 4.4 ملاحظات الحتمية والاعتماد

- `src/utils/discoveryEngineCore.ts` يستخدم `Math.random()` للخلط العشوائي، و`performance.now()` للوقت؛ لذا لا يضمن نفس ترتيب الاكتشاف لكل تشغيل.
- أجزاء UI التي فُحصت تعتمد على imports محلية وfixtures؛ لم يظهر استدعاء Python أو API backend في شجرة الاستيراد.
- الوحدات `src/utils/discoveryEngine.ts`, `expandedPatternScan.ts`, `proposedEquations.ts` لم يظهر لها مستهلك داخل مسار App/components/scripts الذي جرى تتبعه؛ تصنف **مرشحة orphan** فقط، وتحتاج reference search شامل قبل أي حذف.
- لا تستخدم نتائج المحرك المحلي في UI بديلاً عن artifacts Python الموثقة.

### 4.5 سكربتات TypeScript/JavaScript خارج src

`scripts/checkData.js`, `checkData.ts`, `executeEmpiricalFramework.ts`, `printStep1.ts`, `runHindcast.ts`, `testCircuitBreaker.ts`, `testForecastEngine.ts` تستورد fixtures ووحدات من `src/data` و`src/utils`. وهي أدوات تشغيل يدوية/تاريخية؛ لا تدخلها `tsconfig.json` ولا يوجد لها Workflow CI مستقل.

## 5. العقود والبيانات وخرائط القراءة/الكتابة

| المورد | قارئ/منتج رئيسي | وجهة/ملاحظة |
|---|---|---|
| `experimental_contracts/**` | Python engine/validator أو Workflow JSON checks | مواصفات مدخلات ومنهجية/حوكمة؛ وجود العقد وحده لا يثبت تشغيله |
| `catalog_first/readiness_gate/macro_plus_eia_energy/**` | Discovery V1 في فرعه المرشح؛ وأدوات readiness القديمة | مخرجات candidate/profiles؛ ملفات خام/مراحل كثيرة خارج Git |
| `campaigns/agents/trade_v1/WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv` | WDI adapter | DomainState JSONL وadapter summary على فرع Discovery |
| `campaigns/agents/**` | DomainState validator وSupervisor gate | قراءة تقارير agents/outputs وتحقق schema/lineage |
| `campaigns/CAMPAIGN_SHARED_GATE_V1/**` | evidence/supervisor gate | سجل قبول/عزل؛ Gate pass لا يعني runtime eligible |
| `data/raw/**` | source manifests/adapters | يحتوي عدد محدود من source snapshots المتتبعة؛ لا يساوي مستودع البيانات الخارجية الكامل |
| `experiments/**` | workflows التاريخية؛ بعض Evidence refs | أرشيف immutable؛ لا يكتب إليه مسار cleanup |
| `artifacts/real_data_stress/**` | P2.2 stress pipeline | ignored by Git؛ يحزم/يرفع كـActions artifact وRelease |

في نسخة `main-phase2` التي فُحصت، ملف `FINAL_SUPERVISOR_ELIGIBILITY_GATE_V1.json` يسجل `status=pass`، لكن `compiled_runtime_eligible=0` و`causal_claims=0`، مع 2 supported-predictive records و31 quarantined. هذا نجاح لفحص بوابة الحوكمة/المحاسبة، لا تشغيل تنبؤ production.

## 6. ملفات البيئة واعتمادياتها

| المجال | الملف المعلن | حالة القفل/التكرار |
|---|---|---|
| Node/React | `package.json`, `tsconfig.json`, `vite.config.ts` | إصدارات npm ranges؛ لا lockfile ظاهر في شجرة main-phase2؛ لا CI build/lint |
| P2.2 Python | `real_data_stress_pipeline/requirements.txt` | ثلاثة متطلبات معلنة؛ `requests` مستخدم في `fetch.py` لكنه غير معلن هناك |
| Catalog tooling | لا يوجد requirements خاص | pandas/matplotlib/numpy بحسب البرامج؛ أصول raw/staged خارج Git في مواضع متعددة |
| Discovery V1 | لا يوجد requirements خاص | معظم الوحدات standard library؛ WEO mirror يحتاج `huggingface_hub` و`pyarrow` ويثبتها workflow مباشرة دون lock |
| Frozen detector | يستخدم numpy | يعتمد عليه P2.2؛ لا تعدل الملف أو تضف dependencies داخله |

## 7. مناطق التداخل/التكرار المحتمل — لا قرارات حذف

1. `real_data_stress_pipeline/run_pipeline.py` و`fetch.py`: كلاهما يتعامل مع snapshots/provenance/HTTP، لكن الأول يستخدم وظائفه الخاصة ولا يستورد SourceFetcher. تداخل مسؤوليات محتمل، لا تثبت أنهما duplicate implementation كاملان.
2. `catalog_first/tooling/**` وWorkflow engines: الأدوات تبني readiness/profiles من raw/staged؛ لا يوجد CI عام يربطها بكل المخرجات. لا تنقلها إلى kernel قبل استكمال reference/data audit.
3. `src/utils/discoveryEngineCore.ts` و`src/utils/discoveryEngine.ts` و`patternDiscoveryEngine.ts`: تحمل أسماء Discovery لكن لها واجهات وبيانات/خوارزميات مستقلة. لا تدمجها أو ترفعها إلى المحرك العلمي.
4. `campaign/` (المفرد) و`campaigns/` (الجمع): الأولى حزمة raw acquisition/coverage مبكرة؛ الثانية Agent/DomainState/evidence orchestration أحدث. اختلاف المحتوى والدور يمنع اعتبارهما نسختين مكررتين تلقائياً.
5. `lightning_logs/version_*/hparams.yaml`: سجلات 15 نسخة تدريب/تشغيل تاريخية؛ لا تُحذف لمجرد أن نقطة الدخول الحالية لا تشير إليها.
6. `experiments/**` يحتوي أشكالاً/إصدارات متعددة للكاشف والـP-engine؛ تشابه أسماء ووظائف لا يجيز الدمج أو الحذف.

## 8. حدود التغطية

- تمت قراءة 43 ملف Python متتبعاً خارج `experiments/**`، و40 ملف TypeScript/JavaScript، وملفات Workflows الـ21 على main-phase2 والستة في Discovery branch.
- تتبع الاستيراد هنا static/grounded في الملفات المقروءة؛ لم يُنفذ Python call-graph آلي كامل على جميع ديناميكيات `importlib` أو أوامر shell.
- لم يتم تثبيت dependencies أو تشغيل الاختبارات محلياً من clone؛ حالات النجاح المشار إليها مصدرها GitHub Actions فقط.
- لم يُفحص كل ملف من 916 ملفاً داخل `experiments/**` لأن هذا الأرشيف protected scope؛ تم احترامه.
- لا تحذف أي مرشح orphan أو وحدة تبدو مكررة قبل فحص branch-wide references، والـworkflow invocation، والـartifact lineage، وhashes.

