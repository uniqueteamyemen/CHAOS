# Event-Path Political Target Contract v1

## العقد

تم فصل المدخل عن الهدف كما يلي:

```text
information available at t
        ↓
Event-Path
        ↓
raw political outcome at t+1 / t+3
```

استخدم المدخل الاقتصادي `ama_gdp_growth_pct` المتاح عند السنة `t`، بينما كان الهدف الخام هو `state_based_conflict` من UCDP عند الأفق المحدد. لم تُستخدم قيمة الهدف المستقبلية في بناء حالات المدخل. استُخدمت النواة العامة نفسها، مع `window_width=3` و`train_size=8` و`min_support=2`، وتجمد المسار داخل كل prefix تدريبي، وامتنع عند ضعف الدعم.

## النتائج

| Horizon | Path accuracy | Majority accuracy | Lift | Supported rows | Coverage | Abstention |
|---|---:|---:|---:|---:|---:|---:|
| t+1 | 0.8756 | 0.8822 | -0.0066 | 1,808 | 0.4703 | 0.5297 |
| t+3 | 0.8871 | 0.8894 | -0.0023 | 877 | 0.2746 | 0.7254 |

## الحكم

الهدف السياسي أصبح الآن صحيحًا وقابلًا للتفسير تقنيًا، لكن Event-Path لم يتفوق على Majority في أي من الأفقين. عند `t+1` كان Lift سالبًا قدره `-0.0066`، وعند `t+3` كان Lift سالبًا قدره `-0.0023`. كما أن coverage تنخفض إلى `0.4703` عند السنة و`0.2746` عند ثلاث سنوات.

هذه النتيجة لا تدعم حاليًا ادعاء أن نمط Event-Path الاقتصادي يتنبأ بالـraw political outcome. وهي أفضل من التشغيل السابق من ناحية صلاحية السؤال، لأن المقارنة أصبحت بين معلومات عند `t` وهدف سياسي خام عند `t+h` بدل توقع state label مشتق من الهدف نفسه.

## قرار min_support

نبقي `min_support=2` ثابتة. النتائج لا تشير إلى أن المشكلة هي threshold؛ بل إن Path المدعوم لم يتفوق حتى على Majority، ورفع العتبة سيخفض coverage أكثر، بينما خفضها سيعيد خطر التنبؤ من دعم ضعيف. لا يوجد مبرر لاختيار عتبة ديناميكية بعد رؤية هذه النتائج.

يمكن مستقبلًا تعريف سياسة عامة تعتمد على **حد أدنى ثابت مع coverage وabstention إلزاميين**، لكن لا يجوز تحويل `min_support` إلى متغير يتم ضبطه لكل مجال بعد الاطلاع على الأداء. إذا احتاج مجال صغير إلى دعم أكبر، فالحكم الصحيح قد يكون `not_testable` لا threshold أقل.

## الحالة

```text
technical_target_contract = valid
predictive_edge_at_t_plus_1 = not_supported
predictive_edge_at_t_plus_3 = not_supported
causal_claims = not_permitted
operational_promotion = rejected
```

لم يُستخدم أي tuning للزلازل أو السياسة أو الاقتصاد، ولم تُعدّل بيانات المصدر أو تعريف Event-Path العام.
