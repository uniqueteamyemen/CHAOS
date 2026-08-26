# تقرير التقدم المتتابع — ثلاث مراحل في CHAOS

## الخلاصة التنفيذية

نُفذت ثلاث مراحل متتابعة دون انتظار اعتماد بين كل مرحلة، وبُني القرار التالي من النتيجة الفعلية لكل مرحلة.

المرحلة الأولى نقلت صيغة high-growth إلى مصدر اقتصادي مستقل هو UN AMA، ونجحت في تكرارها بصورة أولية. المرحلة الثانية نقلت السؤال إلى domain مختلف، هو UCDP Organized Violence Country-Year، وفشلت في إظهار علاقة تتجاوز Null Controls. المرحلة الثالثة دمجت الدليلين في سجل نمط محكوم.

النتيجة الحالية ليست «النمط يعمل في كل شيء»، وليست «كل ما ظهر كان صدفة». الأدق هو:

```text
high current GDP growth (>4%)
→ material GDP deterioration within 3 years
```

لها تكرار اقتصادي مستقل أولي، بينما لم يظهر من الاختبار الحالي دليل على أن الصيغة نفسها تتنبأ بوجود صراع مسلح أو بعنف مرتفع في UCDP بعد ثلاث سنوات.

## المرحلة الأولى — UN AMA Economic Replication

استُخدمت ملفات UN Statistics Division National Accounts Main Aggregates المرفوعة في يناير 2026. غُيّر المصدر وتعريف الناتج، لكن جُمّدت القاعدة والنتيجة قبل قراءة أرقام AMA:

```text
ama_gdp_growth_pct[t] > 4.0
→ ama_gdp_growth_pct[t+3] <= ama_gdp_growth_pct[t] - 2pp
```

| Split | Origins | Balanced Accuracy | F1 | Positive outcomes |
|---|---:|---:|---:|---:|
| Discovery fit 2003–2009 | 1,472 | 0.6701 | 0.5547 | 440 |
| Discovery inner 2010–2012 | 636 | 0.7286 | 0.6160 | 191 |
| Validation 2013–2016 | 848 | **0.7325** | **0.6185** | 253 |
| Confirmation 2017–2019 | 636 | **0.6821** | 0.5038 | 150 |

تم تشغيل 2,000 label permutation داخل الدولة لكل من validation وconfirmation. كانت `p=0.0005` في كليهما. لذلك سجلت المرحلة كـ`independent-source descriptive replication: supported provisionally`.

هذا لا يثبت السببية. AMA يذكر أن بعض السلاسل قد تستخدم إجراءات تقدير عند غياب البيانات الرسمية، ولذلك بقيت provenance والـmetadata جزءاً من الحكم.

## المرحلة الثانية — Cross-Domain AMA × UCDP

استخدمت UCDP Organized Violence Country-Year 26.1 كما هو، وهو dataset سنوي أصلي. لم أُحوّل UCDP GED اليومي إلى annual values. رُبطت الحالات بالاسم المعياري للبلد والسنة فقط، وسُجلت المطابقات والفجوات.

| المؤشر | القيمة |
|---|---:|
| AMA rows | 12,100 |
| UCDP Country-Year rows | 7,132 |
| matched rows | 5,762 |
| matched UCDP countries | 163 |
| horizon | 3 سنوات |
| rule | AMA GDP growth >4% |
| previous locked test reopened | لا |

اختُبرت نتيجتان مستقلتان من UCDP:

### وجود صراع قائم على الدولة

| Split | n | Observed BA | F1 | Null BA mean | p |
|---|---:|---:|---:|---:|---:|
| Validation 2013–2016 | 651 | 0.5833 | 0.3684 | 0.5870 | 0.7701 |
| Confirmation 2017–2019 | 489 | 0.6142 | 0.4248 | 0.6123 | 0.6007 |

لم تتجاوز القاعدة null. لذلك سُجلت هذه الفرضية `not supported by current cross-domain null`.

### عنف قائم على الدولة مع 25 وفاة أو أكثر

| Split | n | Observed BA | F1 | Null BA mean | p |
|---|---:|---:|---:|---:|---:|
| Validation 2013–2016 | 651 | 0.5788 | 0.3019 | 0.5801 | 0.6712 |
| Confirmation 2017–2019 | 489 | 0.6490 | 0.3717 | 0.6365 | 0.1509 |

confirmation أعلى من null mean، لكنها لم تتجاوز الحد المحسوب ولم تحقق دليلاً كافياً. لذلك سُجلت `weak_or_unresolved_cross_domain_signal`، لا نجاحاً.

## المرحلة الثالثة — سجل النمط والقرار

تم إنشاء `CONTROLLED_PATTERN_REGISTRY_V1.jsonl` بأربع حالات منفصلة:

| Pattern | Status |
|---|---|
| High-growth → material GDP deterioration | `provisionally_supported_descriptive` |
| High-growth → future state-based conflict | `not_supported_by_current_cross_domain_null` |
| High-growth → high-fatality state-based violence | `weak_or_unresolved_cross_domain_signal` |
| Bounded population/energy proxy as additive second node | `rejected_as_additive_node` |

هذا الفصل يمنعنا من تحويل نجاح اقتصادي إلى ادعاء سياسي أو صراعي بلا دليل. النموذج لم يستخرج حتى الآن «شبكة سببية عامة»؛ استخرج علاقة اقتصادية وصفية قابلة للتكرار الأولي، وفشل نقلها إلى outcome صراعي.

## قرار التنفيذ التالي

أرى أن أفضل قرار ليس إيقاف العمل ولا فتح تجارب عشوائية جديدة. القرار هو تثبيت ما نجح وتغيير ما فشل:

1. نحتفظ بالمسار الاقتصادي `high-growth → material deterioration @3y` كمرشح وصفي فقط.
2. لا نضيف population أو energy/GDP كعقدة ثانية في النسخة الحالية.
3. لا نستخدم المسار الاقتصادي الحالي للتنبؤ بالصراع؛ UCDP لم يدعمه.
4. إذا استمر البحث، ننتقل إلى مصدر اقتصادي مستقل ثانٍ أو نختبر مساراً متأخراً مختلفاً داخل AMA/UCDP بعقد جديد، لا إلى إعادة اختيار thresholds بعد النتائج.
5. تبقى الترقية التشغيلية مرفوضة إلى أن يتكرر النمط في مصدر مستقل آخر أو يظهر domain outcome مستقل مع null/stability مناسبين.

## الحوكمة والحالة

تم حفظ المصادر الخام، ملفات staging، العقود، المقاييس، null replicates، سجل المطابقات، التقرير، وسجل pattern registry داخل CHAOS. لم تُستخدم imputation أو normalization أو source averaging، ولم تُحول بيانات GED اليومية إلى annual values. بقي `market-intelligence-engine` دون تعديل.

### References

[1]: https://unstats.un.org/unsd/snaama/downloads "UN Statistics Division — National Accounts AMA Downloads"
[2]: https://unstats.un.org/unsd/snaama/ "UN Statistics Division — National Accounts Main Aggregates"
[3]: https://ucdp.uu.se/downloads/ "UCDP Dataset Download Center"
[4]: https://www.rug.nl/ggdc/productivity/pwt/?lang=en "Penn World Table 11.0 — alternative independent source screened"
