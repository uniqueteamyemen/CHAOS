# CHAOS Governance Kernel MVP v1

## القرار

بعد إغلاق آخر محاولة تنبؤية على بيانات IMF IMTS بالحالة `rejected`، انتقل المشروع إلى **Governance Kernel MVP**. هذا لا يعني حذف البحث التاريخي أو الادعاء أن التنبؤ مستحيل؛ بل يعني إيقاف مطاردة الإشارات الحالية وتحويل القيمة المتحققة إلى طبقة تحقق مستقلة تحفظ الأدلة والنتائج السلبية وقابلية إعادة التشغيل.

## ما الذي بُني؟

النواة موجودة في `chaos_governance_kernel/` وتحتوي على:

| المكوّن | الوظيفة |
|---|---|
| Registry/hash | تسجيل كل artifact بمساره ودوره وحجمه وSHA-256 |
| Manifest validation | كشف الملفات الناقصة وتغير الحجم أو hash والتكرار في المسارات |
| Deterministic replay | تشغيل command معلن والتحقق من hashes المخرجات |
| Data audit | فحص الأعمدة المطلوبة، duplicate keys، نطاق السنوات، null counts، frequency declaration، وتسرب الهدف |
| Provenance ledger | سجل JSONL append-only لكل فحص وقرار |
| Evidence Graph | ربط bundle بالـartifacts وreplay والقرار |
| Admission semantics | حفظ `admitted/quarantined/rejected/not_testable` دون إعطاء rejected وزناً إيجابياً |

النواة لا تدعي صحة النموذج أو السببية. هي تتحقق من سلامة سلسلة الدليل.

## الاختبار على حالة حقيقية

اختُبرت النواة على حزمة حقيقية لمسار `TRADE_REGIME_TRANSITION_DISCOVERY_V1`، وهي تشمل العقد، البروتوكول، state panel، الأحداث، rolling metrics، subwindows، null summaries، summary النهائي، وTransitionEvidence.

| الاختبار | النتيجة |
|---|---|
| تسجيل 9 artifacts حقيقية | PASS |
| تطابق SHA والحجم | 9/9 PASS |
| state panel | 3,375 صفاً، 2000–2024، annual، duplicate keys=0، PASS |
| events | 180 حدثاً، 2005–2024، duplicate keys=0، PASS |
| replay لـTransitionEvidence | PASS؛ المخرج مطابق للـSHA |
| Evidence Graph | 12 nodes / 12 edges |
| تغيير hash متعمد | مرفوض كما يجب |
| duplicate key متعمد | مرفوض كما يجب |
| target leakage متعمد | مرفوض كما يجب |
| نتيجة البحث الأصلية | `rejected`، محفوظة ولا تدخل positive composition |

## دلالة المنتج

النواة ليست بديلاً عن MLflow أو OpenLineage أو أدوات observability أو منصات AI governance الشاملة. موضعها المحتمل هو **independent evidence and replay assurance** عبر أدوات متعددة، بحيث يستطيع فريق التدقيق الإجابة عن الأسئلة التالية:

```text
ما البيانات والإصدار والـhash الذي استُخدم؟
ما الكود والأمر والـseed؟
هل يمكن إعادة تشغيل النتيجة؟
هل حدث تسرب زمني أو خلط تواتر أو duplicate key؟
ما الذي فشل أو رُفض، ولماذا؟
هل قرار الاعتماد مدعوم بالأدلة أم معزول في quarantine؟
```

## الحدود الحالية

الإصدار الحالي CLI/stdlib ومحلي. لم يُبنَ بعد نظام مستخدمين أو SaaS أو عزل متعدد المستأجرين أو تكاملات مؤسسية واسعة. كما أن `data-audit` الحالي يعتمد على قواعد schema معلنة في الأمر، ولا يدعي أنه يفهم دلالة كل مجال تلقائياً. هذه حدود مقصودة لإثبات النواة قبل الاستثمار في واجهة أو بنية سحابية.

## الخطوة التجارية التالية

لا ينبغي إطلاق منتج واسع قبل مقابلة design partners. الاختبار التالي يجب أن يكون pilot صغيراً مع pipeline حقيقية لدى مؤسسة تستخدم نماذج أو تحليلات حساسة، ويقيس وقت إعداد evidence pack، وقت إعادة التحقيق، وعدد مشكلات السلامة التي يكتشفها النظام. إذا لم يظهر توفير قابل للقياس أو التزام من عميل، تبقى CHAOS Governance قدرة داخلية لا منتجاً تجارياً.

## مراجع تقنية داخلية

- `chaos_governance_kernel/core.py`
- `chaos_governance_kernel/checks.py`
- `chaos_governance_kernel/cli.py`
- `experiments/governance_mvp_v1/trade_regime_transition_audit/GOVERNANCE_BUNDLE_MANIFEST_V1.json`
- `experiments/governance_mvp_v1/trade_regime_transition_audit/GOVERNANCE_KERNEL_MVP_TEST_REPORT_V1.json`
