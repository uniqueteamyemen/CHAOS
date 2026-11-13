# BRANCH LAST MODIFIED — review/abc-adversarial

> **آخر تعديل (last modified): 2026-11-14 01:43 (+03:00)**
> هذا الملف يعلن تاريخ ووقت آخر تعديل على هذا الفرع، ليَعلم أي شخص يفتحه أن هذه أحدث نسخة.

| البند | القيمة |
|---|---|
| الفرع | `review/abc-adversarial` |
| **آخر تعديل** | **2026-11-14 01:43 (+03:00)** |
| أساس الفرع | `feat/erp-shadow-mode` |
| الحالة | **محلي فقط — غير مدفوع (not pushed)، ولا PR مفتوح** |

## ما يغيّره هذا الفرع

1. `experiments/identity_lab/exp_j_erp/reconcile.py` — `used_receipt_ids` (منع إعادة استخدام الإيصال)، هوية (picking+product)، فحص "المنتج الغريب"، معامل `quantity_tolerance_relative`.
2. `experiments/identity_lab/exp_j_erp/hybrid_reconcile.py` — هوية مركبة (picking+product) + فحص "المنتج الغريب".
3. `experiments/identity_lab/exp_j_erp/shadow_mode.py` — `run_b` يستدعي الدفعة الكاملة بتسامح نسبي بدل شحنة-بشحنة.
4. `experiments/identity_lab/exp_j_erp/adversarial_abc.py` — **جديد**: 3 حالات (فخّ كمية، متعدد المنتجات، إعادة استخدام) + بوابة انحدار تفشل CI إن عاد العيب.
5. `.github/workflows/erp-reconcile-tests.yml` — خطوة تشغيل الحالات المتخاصمة.
6. `experiments/identity_lab/run_all.sh` — إدراج الحالات المتخاصمة.

## النتائج (40 بذرة)

| الحالة | A | B | C |
|---|---|---|---|
| فخّ كمية = 5 (ادعاء فاقد كاذب) | 40 | 0 | 0 |
| picking متعدد المنتجات (مؤكد) | 0 | 80 | 80 |
| إعادة استخدام إيصال (مؤكد) | 80 | 40 | 0 |

## التحقق

- 40/40 اختباراً موجوداً يمر (لا ارتدادات).
- المعيار الأصلي (720 حالة) لم يتغيّر.
- بوابة الانحدار المتخاصمة: **exit 0**.
- A تُرك مجمّداً عمداً (محرك legacy للمقارنة).

## ملاحظات

- لم يُدفع أي شيء إلى GitHub؛ كل التغييرات محلية على هذا الفرع.
- خطأ اختبار `tempfile` بيئي (قيد sandbox على إنشاء مجلدات مؤقتة)، لا علاقة له بالكود.
