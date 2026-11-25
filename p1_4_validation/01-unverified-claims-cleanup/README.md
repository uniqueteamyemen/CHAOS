# المرحلة الثانية — P1.4 REPAIR / إبطال الأرقام غير المسندة

**الفرع:** `feat/p1-4-capability-envelope-pilot-v1-20261125`  
**Commit الذي جرى تصحيحه:** `8a88cfcce173355270ccd08ece8272fdfb3f7cc4`  
**نطاق الإصلاح:** هذا الفرع فقط. لم تُعدّل `main-phase2` أو أي فرع آخر أو PR آخر.

## تسمية المشروع والمرجع

- مسار التحقق: **P1.4**.
- المحرك موضوع التقييم: **P2-C@86cb8e5**.
- Commit المرجع الكامل: `86cb8e576dc0bd21044743dd2749f5bf1d8899ff`.
- لا يعني هذا الإصلاح تعديل P2-C أو تغيير مرجعه.

## ما تم إصلاحه في ملفات هذا الفرع

1. **Capability Envelope:** إزالة تكرار `40_initial_calibration_observations` مع إضافة اختبار يثبت فرادة عقد 40/20 وحد أهلية FOCuS.
2. **Protocol:** إزالة العدد المتوقع الثابت للحالات التي ستفشل Threshold 90، وإزالة سقف التنفيذ العددي الموروث. لا يُثبت عدد حالات Threshold 200 أو عدد السلاسل المنفذة قبل صدور Artifacts أصلية.
3. **Threshold 200:** محاولة واحدة عند الموضع المحدد مسبقاً، للحالات من Stratum-106 التي يثبت Artifact Threshold 90 أنها غير قابلة للمعايرة. IDs والعدد مشتقان من Artifact، لا من تخمين سابق. يعاد استخدام Null max-statistics نفسها.
4. **Stratum-32:** يبقى تصنيفاً موثقاً ضمن تقسيم عينة C1 المختارة؛ لا يُستخدم كهدف لامتداد Threshold 200.
5. **نطاق التنفيذ:** C1 selected sample فقط. يدخل التنفيذ كل مرشح مؤهل وفق Artifacts المعايرة وقواعد الأهلية. عدد السلاسل والحالات يُشتق من Artifacts؛ لا سقف عددي إضافي ولا إحلال لهويات العينة.
6. **Track B:** يقتصر على حالات C1 التي تثبت Artifacts أنها غير قابلة للمعايرة بعد الخطوات المسموح بها. لا حقن فيها، ولا IDs ثابتة، ولا مجموعات مقارنة مفترضة.
7. **Rearm:** القياس التجريبي لا يزال `NOT_RUN`. خطة القياس تستخدم 1000 HOLDOUT Null traces لكل سلسلة/موضع؛ هذا عدد تكرارات مخطط، وليس نتيجة قياس.
8. **الاختبارات:** استبدال Assertions التي كانت تعامل نتائج غير منفذة كحقائق باختبارات تربط الحالة بالأدلة وتمنع عودة حقول النطاق القديم.
9. **Workflow:** `CHAOS P1.4 Capability Contract Gates` يدوي عبر `workflow_dispatch` فقط، ويشغّل اختبارات Capability وProtocol وInjection Runner وربط Cohort. لا يوجد Push أو Pull Request trigger لهذا الـWorkflow.
10. **Workflow اختيار العينات:** بقي يدوياً فقط، ولا يُشغّل تلقائياً عند Push.

## ما حُفظ دون تغيير

- `p1_4_validation/cohort_manifest.json` وهويات C1/C2 المختارة.
- `scripts/p1_4/build_cohort_selection.py` ومنطق الاختيار.
- Artifact اختيار Cohorts التاريخي: Run `45557117680`، Artifact `14995009654`، مع SHA-256 المسجل في البروتوكول. هذا دليل اختيار وربط هويات فقط؛ لا يثبت المعايرة أو أداء الكواشف.
- `A_FAST` و`A_CONSENSUS`.
- مرجع `P2-C@86cb8e5`.

## ما لم يحدث بعد

| البند | الحالة |
|---|---|
| Threshold 90 calibration | `NOT_RUN` |
| Threshold 200 | `NOT_RUN` |
| Rearm overlap measurement | `NOT_RUN` |
| Track B diagnostics | `NOT_RUN` |
| P1.4 injection execution | `NOT_RUN` |
| GitHub Actions Contract Gates على Commit الإصلاح | لم تُشغّل بعد |
| Scientific PASS/FAIL | غير متاح |

لا ينشئ هذا الإصلاح نتائج علمية أو Run Manifest أو Artifact نتائج. لا يجوز وصف المرحلة بأنها خضراء قبل تشغيل الـWorkflow يدوياً ورؤية نجاح كل الاختبارات على Commit الإصلاح نفسه. ولا يجوز بناء Workflow معايرة أو `run_pilot.py` قبل إغلاق هذه البوابة.
