# تقرير الاختبار الإحصائي لاعتماد reporter على الشركاء

## النتيجة التنفيذية

تم تشغيل عقد `IMF_IMTS_DOMINANT_PARTNER_DEPENDENCE_CONTRACT_V1` فعلياً على بيانات IMF IMTS وهدف GDP الموجود في لوحة CHAOS. لم يُستخدم GDP لاختيار الشركاء، واختيرت الشراكات من نافذة 2000–2004 فقط. أنشأ الاختبار 75 صف اختيار، و255 صف reporter-year للأصول من 2005 إلى 2021، على 15 reporter.

الحكم النهائي هو:

> **`not_testable` — وليس `supported_predictive` ولا `rejected` النهائي.**

السبب الأساسي هو ندرة exposure في confirmation: حدث تعرض تفاعلي واحد فقط خلال 2019–2021، بينما العقد يتطلب خمسة على الأقل. كذلك كانت كل فروق المخاطر في confirmation سالبة، وفشل concentration gate، وكان partner-identity null ثابتاً وغير مفيد استدلالياً بسبب بنية العينة الصغيرة.

## تصميم الاختبار

| العنصر | المثبت في العقد |
|---|---|
| المصدر التجاري | IMF IMTS `IMF.STA:IMTS(1.0.0)` |
| المؤشر | `XG_FOB_USD`، صادرات السلع FOB بالدولار |
| نطاق reporter | 15 اقتصاداً |
| الشركاء | أعلى 5 أكواد مؤهلة حسب متوسط الحصة الخام في 2000–2004 |
| الاعتماد | baseline mean share ≥ 20% |
| الصدمة | raw bilateral exports عند t < 70% من t−1 |
| الهدف | GDP growth عند t+h أقل من GDP growth عند t بمقدار ≥2 نقطة مئوية |
| horizons | 1، 2، 3 سنوات |
| fit | 2005–2013 |
| validation | 2014–2018 |
| confirmation | 2019–2021 |
| outcome null | 10,000 permutation داخل reporter |
| partner-identity null | 10,000 fixed-slot permutation داخل reporter |
| cluster bootstrap | 5,000 reporter-cluster resamples |

لم تُستخدم أي عملية log أو normalization أو smoothing أو imputation أو missing-as-zero أو frequency conversion. حُفظت القيم الثنائية الخام قبل وبعد كل حالة تعرض.

## النتائج حسب الفترة والأفق

| split | horizon | rows | positive exposures | positive GDP outcomes | exposed outcomes | risk difference |
|---|---:|---:|---:|---:|---:|---:|
| fit | 1 | 135 | 5 | 40 | 0 | -0.30769 |
| fit | 2 | 135 | 5 | 44 | 0 | -0.33846 |
| fit | 3 | 135 | 5 | 40 | 0 | -0.30769 |
| validation | 1 | 75 | 1 | 8 | 1 | +0.90541 |
| validation | 2 | 75 | 1 | 20 | 1 | +0.74324 |
| validation | 3 | 75 | 1 | 20 | 0 | -0.27027 |
| confirmation | 1 | 45 | 1 | 25 | 0 | -0.56818 |
| confirmation | 2 | 45 | 1 | 14 | 0 | -0.31818 |
| confirmation | 3 | 45 | 1 | 15 | 0 | -0.34091 |

أقل فرق سلبي في confirmation كان عند horizon 2، وقيمته `-0.31818`. التعرض الوحيد في confirmation وقع لدى `SAU` في 2020، لكنه لم يتبعه outcome إيجابي لتدهور GDP في أي من الآفاق الثلاثة.

## partner-identity null

أُعيد إسناد عدد الخانات المهيمنة داخل كل reporter بين الشركاء الخمسة المختارين، مع تثبيت reporter والقيم الثنائية الخام وتوقيت الصدمات والنتائج. لم تتغير قيمة max-stat في أي من 10,000 تكرار؛ كان:

```text
p = 1.0
null mean = -0.3181818
null SD = 0.0
null q95 = -0.3181818
```

هذه ليست دليلاً على أن هوية الشريك غير مهمة. السبب الأدق هو أن confirmation لا تحتوي إلا على صف تعرض واحد: `SAU, 2020`، وفيه شريكان متعرضان للصدمة من أصل خمسة شركاء مختارين، مع أربع خانات dominant. في هذه البنية، كل إعادة إسناد لأربع خانات من أصل خمسة تلتقط واحداً على الأقل من الشريكين المتعرضين، فيبقى exposure ثابتاً. لذلك فالضابط **degenerate/non-informative** في هذه العينة، وليس ضابطاً ناجحاً.

## outcome null وbootstrap

حافظ outcome null على exposure الحقيقي وبدّل outcome labels داخل reporter. نتج:

| الإحصاء | القيمة |
|---|---:|
| outcome-null p-value | 1.0 |
| null mean | 0.36257 |
| null SD | 0.44455 |
| null q95 | 0.70455 |
| cluster-bootstrap mean | -0.32277 |
| cluster-bootstrap 2.5% | -0.35714 |
| cluster-bootstrap 97.5% | -0.27273 |

يظهر bootstrap أن الفرق المرصود سلبي في هذه العينة، لكن لا ينبغي استخدام ذلك كفاصل تنبؤي قوي، لأن عدد exposures صغير جداً.

## اختبارات الحوكمة

| البند | الحكم |
|---|---|
| coverage minimum | فشل: exposure واحد في confirmation بدلاً من خمسة |
| reporter stability | فشل |
| concentration | فشل: reporter واحد يساهم بـ3 من أصل 7 exposure rows، أي 42.86%، فوق حد 40% |
| confirmation direction | سالب في الآفاق الثلاثة |
| identity null | p=1.0 وSD=0؛ degenerate |
| outcome null | p=1.0 |
| causal claim | ممنوع |
| Composer positive weight | ممنوع |
| runtime promotion | ممنوع |

## القرار العلمي

هذه الجولة فتحت بنية IMTS الجديدة فعلياً، لكنها لم تنتج Edge قابلة للتركيب. لا يجوز تفسير النتيجة على أنها نفي عام لأهمية الاعتماد التجاري أو هوية الشريك. النتيجة القابلة للتدقيق أضيق:

```text
ضمن 15 reporter، وخمسة شركاء مختارين من 2000–2004،
وبتعريف contraction عند 30%،
وبهدف GDP deterioration عند 1–3 سنوات،
لم توفر confirmation كثافة تعرض كافية،
وكان الفرق المرصود سالباً.
```

التوصية المنهجية هي عدم إعادة تشغيل العقد نفسه بتغيير العتبات بعد رؤية النتيجة. إذا أردنا الاستمرار، يجب أن يكون ذلك بعقد جديد يغير السؤال فعلاً، مثل اختيار نافذة تاريخية أوسع قبل تجميد العقد، أو استخدام صدمة مشتركة محددة المصدر، أو توسيع reporter coverage قبل الاختبار. أي تغيير في selection window أو عدد الشركاء أو dominance threshold أو null procedure يستلزم version جديداً.
