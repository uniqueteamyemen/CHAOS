# Experiment E — robustness, and whether D3 can name what it sees

Clean runs: **30 seeds**. Transfers are noise-free by construction, so the D3 table is
structural, not statistical: it reports what the classifier decides, not how often.

## 1. False alarms on clean data

| detector | alerts over 30 seeds | per run |
|---|---|---|
| D1 identity | 0 | 0.00 |
| D2 structuring | 0 | 0.00 |
| D3 edge | 0 | 0.00 |

## 2. Can D3 name the outcome?

| scenario | loss obs. | loss cases | delay | unmatched | ambiguous | ok | verdict |
|---|---|---|---|---|---|---|---|
| clean | 0 | 0 | 0 | 0 | 0 | 12 | silent |
| loss | 12 | 1 | 0 | 0 | 0 | 0 | loss |
| delay1 | 0 | 0 | 0 | 0 | 0 | 12 | silent |
| delay2 | 0 | 0 | 12 | 0 | 0 | 0 | delay, not loss |
| no_id | 0 | 0 | 0 | 0 | 0 | 12 | matched by fallback, no false loss |
| dup_id | 0 | 0 | 0 | 0 | 12 | 0 | ambiguity reported, no loss claimed |
| unmatched | 0 | 0 | 0 | 12 | 0 | 0 | unmatched reported, no loss claimed |
| nested | 0 | 0 | 0 | 0 | 0 | 24 | silent |

## ما أثبته كل صف

- **loss**: 12 ملاحظة شهرية تساوي **حالة واحدة مستمرة** — لا 12 كسرًا. العمودان منفصلان عمدًا.
- **delay1**: التسليم في الشهر التالي لا يُصنَّف خسارة إطلاقًا — صفر في عمود loss.
- **delay2**: تأخر شهرين يُصنَّف **تأخرًا** لا خسارة، ويُعدّ تجاوزًا للتسامح المعلن.
- **unmatched**: الطرف المرسل بلا سجل مقابل → `unmatched`، ولا ادعاء خسارة. الفرق مهم:
  الخسارة ادعاء عن كمية، و`unmatched` ادعاء عن سجل ناقص.
- **dup_id**: معرّف مكرر يُعلن **غموضًا** ويتوقف التصنيف، بدل أن يجمع حركتين في حافة واحدة.
- **no_id**: يعمل بالمطابقة البديلة (من/إلى/الشهر) ويُعلن `matched_by_fallback`، لكن دقته
  تصبح دقة مطابقة لا دقة كشف — وهذا يظهر كضعف لا كخطأ.
- **nested**: تحويلان متداخلان A→B→C في الشهر نفسه لا يولّدان إنذارًا كاذبًا.

## 3. الحد الذي لم تُثبته هذه التجربة

البيانات كلها مصطنعة، والتحويلات بلا ضجيج في الكمية. لذلك رقم D3 هنا يقيس **المنطق**، لا
الحساسية الاحتمالية. أما D1 وD2 فرقمهما يقيس احتمال الإنذار الكاذب فعليًا (30 بذرة، σ ≈ 2.16).

والفصل بين «خسارة» و«تأخر» و«سجل ناقص» صار مبنيًا في الكود، لكنه يعتمد على تسامحين معلنين:
شهر واحد للتأخر، و1 وحدة للتقريب. تغييرهما يغيّر التصنيف، ويجب أن يُجمَّدا
مثل أي معامل آخر.
