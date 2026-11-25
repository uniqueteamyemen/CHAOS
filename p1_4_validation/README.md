# P1.4 Evidence-First Execution

هذه نقطة الدخول الوحيدة لتنفيذ P1.4 وإغلاق P2-C. الحسابات والاختبارات والمعايرات كلها في GitHub Actions.

## التسلسل
1. Preflight: تثبيت بيانات المصدر وCohorts ومعرّفات G1.
2. Threshold 90: معايرة FOCuS وHuber MAD وHuber Bartlett لكل سلسلة C1 ولكل موضع 0.30/0.50/0.70، مع 1000 Development و1000 Holdout لكل موضع.
3. Threshold 200: تطبيق مرة واحدة على حالات عدم المعايرة الفعلية من Artifact 90؛ لا قص لفرض العدد 7 ولا Threshold 500.
4. Track B: AR(1)/AR(p)، GARCH(1,1)، ARCH-LM، lag-12، trend، FOCuS original candidates وnull distribution.
5. Rearm: 1000 مسار null مستقل لكل سلسلة مؤهلة وقياس تداخل نقاط الحقن مع نافذة 20.
6. Pilot: 15 سلسلة C1 كحد أقصى × 19 حالة =285 حالة عند اكتمال 15.
7. قرار P2-C مقيد بالأفواج المنفذة؛ لا ترقية C2/C3 بالاستنتاج.

## المصادر
- P2.2 prepared artifact 14857826243؛ SHA-256 c83f6e960296fbbdb687650a798959f08cb8d98db68de8ca713d7be278e824fe.
- Cohort selection artifact 14995009654؛ ZIP SHA-256 fa67b9c79e5867a0d799c981903e3a44b9b7b680bb2a844a25dfd2a91bf31e0b.
- G1 shards الأربعة مثبتة ببصماتها داخل الـWorkflow.
- A_FAST وA_CONSENSUS مرجعان لا يعدلهما هذا المسار.

## Replay
```bash
python p1_4_validation/run_evidence_pipeline.py --phase all --prepared-zip /tmp/p2-prepared.zip --manifest p1_4_validation/cohort_manifest.json --protocol p1_4_validation/pilot_protocol.json --selection-json /tmp/cohort_selection.json --g1-shards-dir /tmp/p2-g1-shards --output artifacts/p1_4/evidence --budget-hours 24
```

NOT_RUN تعني لم ينفذ. NOT_ELIGIBLE تعني عدم تحقق الأهلية. INCONCLUSIVE تعني عدم كفاية الأدلة. Pilot C1-only لا يثبت C2/C3، وPARTIAL_VALIDATION ليست صلاحية إنتاجية.
