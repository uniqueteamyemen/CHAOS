# اختبار PMR داخل المجال — النتيجة

## نطاق الاختبار

استُخدم أرشيف OECD Product Market Regulation 2013 الرسمي [1] كما هو، على `OBS_VALUE` الخام فقط. أُبقيت التواتر `source_defined_wave`، واستخدمت السلاسل التي تملك قيمة غير مفقودة في كل موجة من 1998 و2003 و2008 و2013. لم تُستخدم مصفوفة سنوية، ولم يُنشأ composite score، ولم تُنفذ interpolation أو imputation أو normalization أو policy-shock labeling.

| الخاصية | النتيجة |
|---|---:|
| raw rows considered | 4,134 |
| complete economy–indicator series | 801 |
| complete economies | 29 |
| complete indicators | 28 |
| adjacent source-wave intervals | 3 |
| null replicates في الاختبار الأول | 10,000 |
| common-wave permutations في الحساسية | 24 كاملة |
| cluster bootstrap replicates | 10,000 |

## النتيجة الوصفية الأولى

قيسَت نسبة الاتجاه الغالب بين التغيرات غير الصفرية في كل فاصل، ثم حُفظ أكبر statistic بين الفواصل الثلاثة. كانت القيم:

| الفاصل | التغيرات غير الصفرية | الزيادة | الانخفاض | التركّز الاتجاهي |
|---|---:|---:|---:|---:|
| 1998→2003 | 663 | 103 | 560 | 0.8446456 |
| 2003→2008 | 580 | 101 | 479 | 0.8258621 |
| 2008→2013 | 631 | 153 | 478 | 0.7575277 |

الـmaximum statistic المرصود هو `0.8446456`. تحت permutation مستقلة لترتيب الموجات داخل كل سلسلة، كان المتوسط الصفري `0.5250546`، والانحراف المعياري `0.0114059`، و`q95=0.5462687`، وempirical `p=0.0001`.

هذه النتيجة تقول إن ترتيب الموجات داخل السلاسل، عند التعامل مع كل سلسلة على حدة، ينتج تركّزاً اتجاهياً أكبر من ذلك null. لكنها لا تقول إن PMR يسبب نتيجة اقتصادية، ولا أن لدينا policy shock، ولا أن الاتجاه موحد في المعنى الاقتصادي؛ اتجاه PMR قد يلتقط تغيرات تنظيمية طويلة الأجل أو خصائص مقياس المصدر نفسه.

## اختبارات الاستقرار والاعتماد

أظهر التفكيك أن الاتجاه الهابط ليس محصوراً في مؤشر أو اقتصاد واحد:

| اختبار الاستقرار | النتيجة |
|---|---:|
| المؤشرات ذات الانخفاض الغالب في الفواصل الثلاثة | 23 من 28 |
| المؤشرات ذات الانخفاض الغالب في فاصلين على الأقل | 27 من 28 |
| الاقتصادات ذات الانخفاض الغالب في الفواصل الثلاثة | 25 من 29 |
| الاقتصادات ذات الانخفاض الغالب في فاصلين على الأقل | 29 من 29 |
| متوسط حصة الانخفاض 1998→2003 | 0.8408327 |
| متوسط حصة الانخفاض 2003→2008 | 0.8342751 |
| متوسط حصة الانخفاض 2008→2013 | 0.7549008 |

هذه الاستمرارية تقوي وصف وجود اتجاه عام في أرشيف PMR، لكنها ترفع أيضاً احتمال أن تكون الظاهرة **اتجاهاً مشتركاً في القياس أو الإصلاحات التنظيمية أو بناء الأرشيف**، لا نمطاً قابلاً للنقل إلى prediction.

## الضوابط الأكثر تحفظاً

لذلك شُغّل ضابط يحافظ على الاعتماد المشترك بين الاقتصاد والمؤشر: أُعيد ترتيب الموجات الأربع بنفس permutation لجميع السلاسل، مع تعداد permutations الأربع والعشرين كاملة. كان `p=1.0` لأن statistic المرصود لم يتفوق على هذا null؛ ثلاث permutations أعطت نفس الحد الأدنى، وبقية permutations أعطت قيماً أعلى. كما أن cluster bootstrap على الاقتصادات أعطى:

| مقياس bootstrap | القيمة |
|---|---:|
| mean max statistic | 0.8489804 |
| SD | 0.0179108 |
| 2.5% quantile | 0.8134711 |
| 97.5% quantile | 0.8838399 |

إذن، بعد الحفاظ على الاعتماد المشترك بين الاقتصادات والمؤشرات، لا توجد إشارة إلى أن ترتيباً زمنياً خاصاً يتفوق على null. وهذا هو الاختبار الأكثر تحفظاً للتفسير العام. أما `p=0.0001` في الاختبار المستقل فينبغي فهمه كدليل على اتجاه واسع داخل هذه العينة، لا كإثبات لنمط تنبؤي مستقل.

## القرار الحوكمي

سُجلت النتيجة الوصفية الأولى بالحالة `not_testable` لأن أربع موجات لا توفر out-of-sample أو entity holdout كافياً. وسُجلت نتيجة الحساسية الاعتمادية بالحالة `rejected` لأن common-wave null أعطى `p=1.0` والـcluster bootstrap احتوى statistic المرصود. لا توجد causal claim، ولا positive Composer weight، ولا runtime promotion.

> **القرار:** PMR يقدم الآن اختباراً حقيقياً قابلاً لإعادة الإنتاج، لكنه لم ينتج Edge تنبؤية. الجديد القابل للاستخدام هو اكتشاف أن أرشيف PMR يحمل اتجاهاً عاماً قوياً، مع فشل الاختبار الأكثر تحفظاً في تمييزه عن اتجاه مشترك/مقاس؛ لذلك يجب عدم حقنه في المحرك.

## الملفات

- `experimental_contracts/OECD_PMR_WITHIN_DOMAIN_TRANSITION_CONTRACT_V1.json`
- `experimental_contracts/OECD_PMR_WITHIN_DOMAIN_STABILITY_NULL_CONTRACT_V1_1.json`
- `experiments/multi_domain_native_edges_v1/pmr_within_domain_v1/PMR_WITHIN_DOMAIN_TRANSITION_METRICS_V1.csv`
- `experiments/multi_domain_native_edges_v1/pmr_within_domain_v1/PMR_STABILITY_SUMMARY_V1.json`
- `experiments/multi_domain_native_edges_v1/pmr_within_domain_v1/PMR_STABILITY_NULL_SENSITIVITY_V1_1.json`
- `experiments/multi_domain_native_edges_v1/pmr_within_domain_v1/PMR_WITHIN_DOMAIN_TRANSITION_EVIDENCE_V1_1.jsonl`

## المرجع

[1]: https://sdmx.oecd.org/archive/rest/data/OECD,DF_PMR,/all?dimensionAtObservation=AllDimensions&format=csvfilewithlabels "OECD PMR Archive SDMX CSV"
