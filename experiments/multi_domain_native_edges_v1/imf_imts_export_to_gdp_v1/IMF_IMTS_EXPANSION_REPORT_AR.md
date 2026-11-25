# توسعة Evidence Library عبر IMF IMTS

## القرار التنفيذي

أضافت الجولة مصدر IMF الرسمي `International Trade in Goods (by partner country) (IMTS)` إلى Evidence Library. هذا المصدر ليس تكراراً بسيطاً لـWDI Trade: فهو يحافظ على أبعاد reporter وcounterpart country وindicator وfrequency، ويقدم صادرات وواردات السلع بقيم مصدرية بالدولار. بطاقة المصدر الرسمية تؤكد أنه successor لـDOTS، وأن التواترات الأصلية Annual وMonthly وQuarterly [1]. كما أكد structure API الرسمي dataflow `IMF.STA:IMTS(1.0.0)` وترتيب الأبعاد الأربعة [2].

> **النتيجة العملية:** نجحنا في فتح مصدر وبنية جديدة قابلة للاستخراج، لكن أول Edge تجارية إلى GDP رُفضت بوضوح؛ لا توجد حالياً حافة IMF IMTS مؤهلة للتركيب.

## ما تم اكتسابه فعلياً

| artifact | النطاق | النتيجة |
|---|---|---:|
| structure response | dataflow `IMF.STA:IMTS(1.0.0)` | HTTP 200، 2,665,607 bytes، 49 codelists |
| bounded reporter/partner extract | 15 reporter، XG وMG، all counterpart، Annual، 2000–2024 | 102,495 observation، 239 counterpart codes |
| world-export edge input | 15 reporter، XG FOB إلى `G001=World`، Annual، 2000–2024 | 375 observation تقريباً/15×25، كل reporters مكتملون |
| source-native adapter | IMTS observations وDomainStates | schema-conformant، بلا تحويل أو imputation |

الخام محفوظ تحت:

```text
campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/raw/
├── imf_imts_query_variants/
├── imf_imts_15_per_reporter/
└── imf_imts_world_export_probe/
```

أهم SHA للاستجابة متعددة البلدان هو `4c1bb8a8921833ccdeae23ea8cae3357f1f330ed42161cfbd6f4dc48f2bb79f8`، وأهم SHA لسلسلة world exports هو `bf3ea685598a2d8c82375064d895c551e8ef778975deb498d33b632ec28a6c49`. الخام غير متتبع في Git بفضل قاعدة ignore.

## جودة التغطية

أنتج adapter `102,495` سجلاً رقمياً في التواتر السنوي من 2000 إلى 2024، عبر 15 reporter و239 counterpart codes ومؤشري `XG_FOB_USD` و`MG_FOB_USD`. جميع reporters الخمسة عشر لديهم سلسلة XG كاملة للسنوات الخمس والعشرين؛ أما MG فالتغطية الكاملة موجودة لأربعة reporters فقط في هذا extract. هذا الفرق محفوظ ولم يُملأ أو يُسوَّ.

التغطية متعددة الشركاء تفتح بنية يمكن أن تدعم لاحقاً مؤشرات source-defined مثل تغير تدفقات reporter–partner أو تركّز الشركاء، لكن هذه المؤشرات لم تُشتق في هذه الجولة ولم تُستخدم في Edge الحالية. لا يجوز اعتبار `limit=5000` اكتساباً عالمياً غير محدود؛ كل query بقي bounded ومذكوراً في provenance.

## Edge الجديدة: export contraction → GDP deterioration

اختبر العقد:

```text
IMF IMTS XG_FOB_USD reporter-to-World عند t
→ WDI GDP growth deterioration عند t+h
```

حُددت حالة المصدر بانخفاض قيمة الصادرات الخام عن السنة السابقة، دون log أو ratio أو percent normalization أو smoothing. وحُددت النتيجة كما في contract السابق: GDP growth عند `t+h` أقل من GDP growth عند `t` بمقدار نقطتين مئويتين أو أكثر. استُخدمت 15 دولة، 2000–2024، origins من 2001 إلى 2021، horizons من 1 إلى 3 سنوات، وتقسيم زمني fit 2001–2013، validation 2014–2018، confirmation 2019–2021.

| split | horizon | rows | contraction positive | outcome positive | risk difference |
|---|---:|---:|---:|---:|---:|
| fit | 1 | 195 | 41 | 43 | -0.21745 |
| fit | 2 | 195 | 41 | 49 | -0.22553 |
| fit | 3 | 195 | 41 | 44 | -0.19306 |
| validation | 1 | 75 | 32 | 8 | -0.02253 |
| validation | 2 | 75 | 32 | 20 | -0.30160 |
| validation | 3 | 75 | 32 | 20 | -0.19259 |
| confirmation | 1 | 45 | 26 | 25 | -0.22267 |
| confirmation | 2 | 45 | 26 | 14 | -0.73684 |
| confirmation | 3 | 45 | 26 | 15 | -0.69838 |

أكبر confirmation risk difference كان سالباً (`-0.2226721`). ضابط null الذي أبقى exposure التجاري ثابتاً وبدّل outcome labels داخل reporter أعطى متوسطاً `0.1218567`، و`p=0.9994001`. كما أن شرط التغطية تحقق، لكن شرط الدعم الإيجابي لم يتحقق. سُجلت الحافة `rejected`، لا `supported_predictive`.

> **المعنى:** ضمن هذه العينة، انخفاض صادرات reporter إلى العالم لم يسبق تدهور GDP بالصيغة المحددة؛ بل كان فرق الخطر سالباً في confirmation. هذا ليس دليلاً على أن التجارة لا تؤثر في الاقتصاد عموماً، بل رفض لهذا التعريف، وهذه العينة، وهذه الفترة، وهذا المصدر.

## قرار Evidence Library والبوابات

أُضيفت DomainStates وTransitionEvidence إلى validators وsupervisor وEvidence Graph. بعد التحديث:

| المقياس | القيمة |
|---|---:|
| DomainState schema | PASS |
| TransitionEvidence schema | PASS |
| graph nodes | 53 |
| graph edges | 54 |
| supported_predictive admitted | 2، من baseline التاريخي السابق |
| quarantined | 25 |
| runtime-eligible | 0 |
| causal claims | 0 |
| IMF IMTS edge | rejected |

لم تحصل حافة IMTS على وزن Composer، ولم تُدخل runtime، ولم يُعدّل `market-intelligence-engine`.

## ما فتحته الجولة فعلاً

الجديد القابل للتقدم ليس Edge إيجابية، بل **بنية تجارية ثنائية مكتملة بما يكفي لبدء سؤال جديد**. المساران المنطقيان لاحقاً هما: اختبار source-defined partner dependence أو export concentration ضد صدمات اقتصادية، أو مقارنة سلاسل IMTS مع Comtrade/WDI كدراسة اختلاف قياس مستقلة. لكن لن يُنفذ أي منهما إلا بعقد جديد يحدد المؤشر قبل رؤية النتيجة، ويضمن coverage كافياً وnull/OOS مناسباً. لا ينبغي إعادة اختبار نفس export-contraction edge بصيغ عتبات متعددة داخل العينة الحالية.

## الملفات الأساسية

- `experimental_contracts/IMF_IMTS_ADAPTER_CONTRACT_V1.json`
- `experimental_contracts/IMF_IMTS_EXPORT_CONTRACTION_TO_GDP_CONTRACT_V1.json`
- `experiments/multi_domain_native_adapters_v1/imf_imts_v1/IMF_IMTS_ADAPTER_RUN_SUMMARY_V1.json`
- `experiments/multi_domain_native_adapters_v1/imf_imts_v1/IMF_IMTS_DOMAIN_STATES_ANNUAL_V1.jsonl`
- `experiments/multi_domain_native_edges_v1/imf_imts_export_to_gdp_v1/IMF_IMTS_EXPORT_TO_GDP_NULL_SUMMARY_V1.json`
- `experiments/multi_domain_native_edges_v1/imf_imts_export_to_gdp_v1/IMF_IMTS_EXPORT_TO_GDP_TRANSITION_EVIDENCE_V1.jsonl`
- `experiments/multi_domain_native_edges_v1/imf_imts_export_to_gdp_v1/IMF_IMTS_EXPANSION_REPORT_AR.md`

## References

[1]: https://data.imf.org/en/datasets/IMF.STA:IMTS "IMF IMTS official dataset card"
[2]: https://api.imf.org/external/sdmx/3.0/structure/dataflow/IMF.STA/IMTS/1.0.0?detail=full&references=all "IMF IMTS official SDMX structure"
