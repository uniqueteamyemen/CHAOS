# exp_p_engine — المحرك الموحّد

> **آخر تحديث: 2026-11-14 (+03:00)**

## ما هو

خط أنابيب واحد يجمع كل ما بُني وبقي صالحاً:

```
بُقيا الهوية
  → خط أساس: انحياز مجمّد + مقياس ضجيج متحرك؛ P1 يستخدم سقفاً، وCUSUM يعمل بمقياس متحرك ويُعلّق عند اكتشاف تغير في نظام الضجيج
  → كواشف: sign-run (P1، σ بسقف 2× الهادئ) و CUSUM (P2، σ متحرك ويُعلّق أثناء حالة الضجيج المرتفع)
  → عدّاد: sign-run break counter (P3)
  → مدير إنذارات: أولوية، كتم P1 محصور بالكيان، تهدئة؛ CUSUM يعيد التصفير تلقائياً بعد إطلاق الإنذار
```

## القرارات المبنية (ولماذا)

| القرار | السبب |
|---|---|
| **فصل مقياس P1 عن P2** | P1 يستخدم σ متحركة بسقف 2× σ الهادئ لحماية التسرب الكبير من ابتلاع الضجيج؛ عندما يتجاوز تقدير الضجيج على نافذة 12 نقطة عتبة 1.5× σ الهادئة، يتحول P1 إلى اختبار اتجاهي يتطلب 13 إشارة متتالية من العلامة نفسها، ويُعلّق CUSUM ويُصفّر مؤقتاً فقط عندما تتجاوز σ القصيرة (12 نقطة) σ الطويلة (52 نقطة) بنسبة 20%، ثم يستأنف بعد استقرار التباين. تُعلن المنظومة حالة degraded؛ وقد تبقى التسربات الصغيرة غير محسومة أثناءها. |
| **نافذة هدوء إلزامية** | حساب الانحياز على كل السلسلة يبتلع التسرب. المحرك يرفض التشغيل بلا نافذة هدوء أو بنقاط غير كافية. |
| **لا STL** | F=1.21 على بُقيا EIA → الموسمية تتساقط جبرياً في طرح طرفي الهوية. |
| **CUSUM تجميعي** | يلتقط الانحرافات الصغيرة المستمرة عندما تتجاوز حساسيته؛ يجب قياس الإنذار الكاذب خارج العينة لكل هوية ومجال قبل التشغيل. |
| **عدّاد sign-run فقط (P3)** | يقيس تكرار كسور sign-run فقط. CUSUM مصدر إنذار مستقل ولا يُدمج قبل اختبار إزالة تكرار موثوق. |
| **كتم P1 محصور بالكيان** | كتم شامل يخفي تسرباً ثانياً مستقلاً. |
| **تصفير CUSUM** | التنفيذ الحالي يعيد التصفير تلقائياً عند إطلاق إنذار؛ لا توجد آلية تأكيد مشغّل في هذه النسخة. |

## الاختبارات

تشمل الاختبارات رفض Sigma هادئة صفرية، وقياس الإنذارات الكاذبة مع الضجيج المتزايد بلا تسرب، واختبار التسرب المتدرج.

- بلا تسرب → صامت.
- تسرب ثابت → P1.
- تسرب صغير (2/شهر) → P2 فقط (CUSUM).
- P1 يكتم P2 لنفس الكيان.
- التهدئة تمنع التكرار.
- تدفق نقدي → نفس السلوك (مجال ثانٍ).
- **الانحياز المجمّد لا يبتلع تسرباً مستمراً**.
- **الضجيج المتزايد بلا تسرب**: يجب أن يُعلن degraded ويوقف CUSUM، مع إبقاء اختبار الاتجاه P1؛ اختبار 40 بذرة يفرض معدل إنذار كاذب لا يتجاوز 10%.
- **نافذة الهدوء إلزامية**، والنقاط غير الكافية تُرفض.
- `adapt` يربط أسماء الأعمدة بالحقول القانونية لهوية حفظ عددية؛ يجب أن تكون القيم العددية وعمود الزمن متوافقة مع عمليات المحرك.

## النطاق والحدود

- **يشمل**: هويات حفظ عددية (مخزون، تدفق نقدي).
- **لا يشمل**: هويات منطقية/عقدية (PayLock H1 — وحدة `exp_a` منفصلة).
- **حدود معلنة**: لا إسناد بلا تسجيل ثانٍ؛ لا كشف مضموناً تحت حساسية الكواشف؛ سقف Sigma يوازن بين عدم ابتلاع الانحراف وزيادة الإنذارات عند تغير الضجيج.

## تكييف المدخلات — عقد صريح للبيانات القادمة

`adapt(rows, mapping)` محوّل أسماء أعمدة إلى الحقول القانونية (`opening`/`inflow`/`outflow`/`other`/`closing`) لهوية حفظ عددية. لا يحوّل أنواعاً اعتباطية ولا يزيل شروط صلاحية الزمن والقيم العددية.

- مصدر جديد متوافق = **mapping جديد**، لا إعادة كتابة للمحرك.
- الحدود الاختيارية (`other`) تفترض صفراً عند غيابها.
- يجب أن يحدد العقد أعمدة عددية متوافقة وعمود زمن قابل للمقارنة الحسابية.

## التشغيل

```bash
python -m unittest experiments.identity_lab.exp_p_engine.test_engine -v
```


## Isolated parallel-fusion experiment (A/B/C)

This experiment is isolated from the production engine.py; A remains the unchanged engine.run() result.

- **A:** current production execution path, including the current alert manager.
- **B:** P1 uses the capped 3-sigma / 3-run candidate rule; positive and negative CUSUM accumulators are independent; both accumulators are held (not erased) while the short/long variance-transition condition is active; CUSUM scale remains unbounded.
- **C:** same independent detector tracks; CUSUM scale is capped at 2 times quiet sigma and transition updates are damped by 0.35 instead of being erased or paused.
- **Fusion:** evidence is aggregated before event adjudication. A reversal or six consecutive calm observations opens a new event. Same-event directional cooldown marks a repeated notification but retains the underlying evidence.

Each run creates an immutable configuration/input snapshot with a SHA-256 input fingerprint, frozen bias, quiet sigma, configuration, code revision, and time range. Out-of-order and duplicate timestamps fail closed.

Run the experiment:

```bash
python -m unittest experiments.identity_lab.exp_p_engine.test_parallel_fusion -v
python -m experiments.identity_lab.exp_p_engine.benchmark_parallel_fusion
python -m experiments.identity_lab.exp_r_grade4.grade4_diagnostics
```

The benchmark runs 500 independent sequences in each declared condition and reports false-alert rates, sensitivity, direction errors, detection delay, and 95% Wilson intervals. It is an experiment, not a production approval: no B/C candidate replaces A unless the paired results justify that decision.
