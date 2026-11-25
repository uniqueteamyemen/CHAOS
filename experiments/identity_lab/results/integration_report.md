# Experiment F — integration of D1, D2 and D3 in one engine

One pass over the data produces two streams that are **not** the same kind of object:

- **breaks**: zero-parameter violations of a frozen identity (`stock_balance`, `transfer_edge`).
- **candidates**: parameterised rules and record conditions (`structuring`, `delay`, `unmatched`, `ambiguous_id`).

## Combined faults: masking and double counting

| scenario | break cases | candidate cases | expected | verdict |
|---|---|---|---|---|
| clean | 0 | 0 | — | PASS |
| leak | 1 | 0 | stock_balance | PASS |
| edge | 1 | 0 | transfer_edge | PASS |
| struct | 0 | 1 | structuring | PASS |
| leak+edge | 2 | 0 | stock_balance, transfer_edge | PASS |
| edge+struct | 1 | 1 | structuring, transfer_edge | PASS |
| leak+struct | 1 | 1 | stock_balance, structuring | PASS |
| all | 2 | 1 | stock_balance, structuring, transfer_edge | PASS |

## ما تقيسه هذه التجربة

1. **لا تحجب الكواشف بعضها.** في `leak+edge` يظهر كسران معًا: تسرّب DIST-B وحافة A→B.
   الكاشف العلائقي لا يرى التسرّب، وكاشف الهوية لا يرى الحافة، وكلاهما يعمل في التشغيل نفسه.
2. **لا ازدواج في التقرير.** كل كسر يظهر مرة واحدة لكل هدف؛ الملاحظات الشهرية تُجمع في حالة
   واحدة قبل العدّ (`to_cases`)، فالفرق بين 12 صفًا وحالة واحدة محفوظ في المخرجات.
3. **الفصل بين الكائنات ليس تجميليًا**: الكسر لا معاملات له، والمرشّح معاملاته معلنة داخل
   الحدث نفسه (`window`, `n_min`, `total_min`, `small_limit`). وهذا يمنع أن يُقرأ مرشّح
   كأنه برهان.

## ما لم تقيسه

- البيانات مصطنعة، والتحويلات بلا ضجيج في الكمية.
- لا يوجد ترتيب أولوية بين الكسور المتزامنة على الهدف نفسه (لم يحدث في هذه التجربة).
- لا يوجد تحكيم بشري: كل المرشّحات تبقى `unreviewed` حتى الآن.

## حالة الإغلاق

بهذه التجربة يُغلق الاختبار المنطقي للمرحلة الحالية. ما تبقّى قبل أي ادعاء أعلى:
بيانات حقيقية، وحوادث موسومة، وتحكيم بشري يبني سجلّ حالات مؤكدة.
