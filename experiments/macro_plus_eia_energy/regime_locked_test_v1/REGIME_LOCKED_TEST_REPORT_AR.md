# تقرير Locked Test — Regime Population وEnergy per GDP

## القرار المختصر

تم فتح locked test مرة واحدة للمسارين اللذين جُمّدا قبل الاختبار:

```text
population path:
target[t] > 4.0 AND population[t-2] <= 75,000,000

energy path:
target[t] > 4.0 AND energy_per_gdp[t-2] <= 10.0
```

استُخدمت outcomes عند `t+3` للسنوات 2020–2024، أي origins من 2017–2021، على 139 كياناً و695 origin. لم يُستخدم test لاختيار proxy أو threshold، ولم يتغير أي مسار بعد رؤية النتائج.

النتيجة الأساسية: **كلا المسارين حققا أداءً أفضل من BA العشوائي 0.5، لكن أياً منهما لم يضف قيمة واضحة فوق baseline يعتمد على high current growth وحده.** كان energy-per-GDP قريباً جداً من baseline الهدف، بل أقل قليلاً؛ وكان population أضعف.

لذلك لا نرقّي عائلة الـregime إلى خوارزمية تشغيلية، ولا ندعي أن bounded population أو energy/GDP يضيفان آلية مستقلة في هذا الاختبار.

## نطاق الاختبار

| العنصر | القيمة |
|---|---:|
| Dataset | `macro_plus_eia_energy_v1_1` |
| Entities | 139 |
| Test origins | 695 |
| Target years | 2020–2024 |
| Origin years | 2017–2021 |
| Outcome | `target[t+3] <= target[t] - 2pp` |
| مسارات مجمدة | 2 |
| Baselines | 5 إضافية |
| اختيار بعد test | ممنوع ولم يحدث |
| raw modification | لم يحدث |
| locked test | نُفذ مرة واحدة |

## المقارنة الكلية

| النموذج | Support | Positive outcomes | Precision | Recall | F1 | Balanced Accuracy | False Alarm Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Population regime | 231 | 243 | 0.5844 | 0.5556 | 0.5696 | 0.6716 | 0.2124 |
| Energy per GDP regime | 269 | 243 | 0.5725 | 0.6337 | 0.6016 | 0.6897 | 0.2544 |
| Target growth > 4 only | 271 | 243 | 0.5720 | 0.6379 | 0.6031 | 0.6906 | 0.2566 |
| Population bounded only | 605 | 243 | 0.3521 | 0.8765 | 0.5024 | 0.5046 | 0.8673 |
| Energy/GDP bounded only | 693 | 243 | 0.3492 | 0.9959 | 0.5171 | 0.4990 | 0.9978 |
| Always negative | 0 | 243 | 0.0000 | 0.0000 | 0.0000 | 0.5000 | 0.0000 |
| Always positive | 695 | 243 | 0.3496 | 1.0000 | 0.5181 | 0.5000 | 1.0000 |

الفرق بين energy regime وtarget-growth-only baseline صغير وسالب: BA=`0.6897` مقابل `0.6906`، وF1=`0.6016` مقابل `0.6031`. هذا يعني أن energy/GDP لم يضف في test قيمة تنبؤية مستقلة واضحة بعد معرفة أن النمو الحالي فوق 4%.

Population regime كان أقل: BA=`0.6716` وF1=`0.5696`. وبالتالي لم تؤكد سنوات test أن bounded population يحسن القاعدة العامة.

## الأداء سنة بسنة

| Target year | Population BA | Energy/GDP BA | Target-growth-only BA | Positive outcomes |
|---:|---:|---:|---:|---:|
| 2020 | 0.5214 | 0.5177 | 0.5217 | 125 |
| 2021 | 0.6571 | 0.6777 | 0.6777 | 20 |
| 2022 | 0.5464 | 0.5728 | 0.5728 | 21 |
| 2023 | 0.8297 | 0.8223 | 0.8223 | 3 |
| 2024 | 0.7564 | 0.7730 | 0.7653 | 74 |

الأداء ليس ثابتاً بالدرجة نفسها كل سنة. 2020، وهي سنة ذات prevalence مرتفع جداً، كانت قريبة من BA العشوائي للمسارات. أما 2023 فعدد outcomes ثلاث فقط، ولذلك لا ينبغي إعطاء BA المرتفع فيها وزناً كبيراً. أفضل قراءة هي أن الإشارة العامة مدفوعة أساساً بنوافذ 2021–2024، مع ضعف واضح في 2020، وليست قاعدة متساوية القوة عبر كل سنة.

## هل نجح المسار في locked test؟

يعتمد الجواب على معنى «نجح»:

| معيار النجاح | الحكم |
|---|---|
| أفضل من BA=`0.5` | نعم، كلا المسارين |
| أفضل من always baselines | نعم من حيث BA، لكن المقارنة لا تكفي وحدها |
| أفضل من high-growth target-history baseline | لا؛ energy أقل قليلاً وpopulation أقل بوضوح |
| إضافة مستقلة من bounded population/energy | غير مثبتة |
| تعميم ثابت عبر كل السنوات | لا؛ 2020 ضعيف و2023 صغير الدعم |
| pattern سببي | لا يمكن استنتاجه |
| ترقية تشغيلية | مرفوضة حالياً |

إذن لا نسجل النتيجة كفشل كامل للمحرك؛ المحرك أعاد تشغيل قواعد مجمدة خارج sample selection وحقق إشارة فوق الصدفة. لكننا نسجل **فشل فرضية الإضافة المستقلة للـbounded proxy فوق high current growth في هذا test**.

## النتيجة العلمية

الجزء الذي بقي قابلاً للدفاع عنه هو:

```text
high current target growth
→ higher historical frequency of material drop within 3 years
```

أما الإضافة:

```text
+ bounded population / energy-per-GDP
```

فلم تضف قيمة مستقلة على locked test. لذلك لا نثبت أن السكان أو كثافة الطاقة يمثلان العقدة الثانية في المسار. قد تكون النتيجة السابقة في validation انعكاساً لاختيار عتبات من grid، أو فرقاً زمنياً، أو تغيراً في تركيب الحالات، أو اعتماداً مشتركاً بين proxy ونمو الهدف.

## ما تم إغلاقه وما لم يُنفذ

تم استخدام locked test مرة واحدة كما حُدد في العقد. لم تُجرَ إعادة محاولة بعتبات أخرى، ولم يُستخدم test لاختيار winner، ولم تُعدل raw أو تُطبق imputation/normalization. لم تُنفذ أي ترقية إلى production، ولم يُقدم أي ادعاء سببي.

النتيجة النهائية للعقد الحالي هي:

```text
population_regime_v1: test-supported above chance, but not additive over target-history baseline
energy_per_gdp_regime_v1: test-supported above chance, but not additive over target-history baseline
operational_promotion: rejected
```

الخطوة التالية، إن لزم الاستمرار، ليست البحث عن threshold أفضل على test. الأفضل هو إعادة تعريف المسار على أساس **high-growth regime وحده** واختبار هل يحتفظ بقيمته في عائلات outcomes أخرى أو في لوحة تاريخية مستقلة، مع اعتبار bounded proxies وصفاً مساعداً لا عقدة مثبتة.
