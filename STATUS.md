# CHAOS — الحالة التنفيذية المرجعية

> **نقطة الدخول الإلزامية:** ابدأ من هذا الملف قبل استئناف أي عمل. هذا الملف يحدد المرحلة النشطة والفرع المرجعي والوثائق التي تحكم التنفيذ.

## هدف المشروع

بناء محرك عملي قابل للتشغيل لرصد التحولات والكسور الهيكلية في السلاسل الزمنية، ثم اختبار ما إذا كانت الإشارات المجمدة تدعم الاستشعار أو التنبؤ خارج العينة. الهدف منتج هندسي يعمل على بيانات حقيقية ويمكن تدقيقه وإعادة إنتاجه؛ ليست الغاية إنتاج ورقة بحثية أكاديمية أو إعلان أداء غير مثبت.

## مرجعية المستودع

- الفرع المرجعي والافتراضي: `main-phase2`.
- آخر خط أساس مدمج: `main-phase2@86cb8e576dc0bd21044743dd2749f5bf1d8899ff` (PR #51).
- لا تُعامل الفروع التجريبية أو PRs غير المدمجة على أنها مصدر حقيقة. جميع الأعمال الجديدة تبدأ من `main-phase2` بعد دمج نقطة الدخول هذه.

## أين نقف الآن؟

### P2-A — فحص البيانات الزلزالية / USGS

**[UNRESOLVED]**

متوقف مرحلياً بعد PR #47. لم يُعتمد null زلزالي، ولا يجوز وصف نتائج الفحص الزلزالي بأنها تحقق إنذار أو صلاحية تشغيلية. تبقى أسئلة اكتمال الكتالوج، والتسجيل، والـcompleteness، والـnull الزمني غير محسومة.

المرجع: [PR #47](https://github.com/uniqueteamyemen/CHAOS/pull/47).

### P2-B — منافسة خط الأساس الاقتصادي على 509 سلسلة

**[COMPLETED]**

أُغلقت ودمجت عبر PR #48 في `main-phase2` عند `3c8eab34`. cohort المثبت: 509 سلاسل (51 Pink Sheet و458 GEM)، منها 359 مؤهلة لتشخيصات stationary-bootstrap null (48 Pink Sheet و311 GEM).

- يحتفظ `A_FAST` حالياً بأفضل خط أساس متوازن للاستخدام المقارن؛ الحساسية المسجلة في تقرير المنافسة: **90.8% / 88.8%**.
- لم تُقبل أذرع Parallel Fusion G–I؛ أظهرت نتائجها عبئاً مرتفعاً من null alarms (42–52%) وإنذارات pre-onset (53–59%).
- هذه النسب تخص بروتوكول P2-B وحقناته، ولا تمثل معدلات إنذار تشغيلية حقيقية. تشخيصات stationary bootstrap مشروطة وليست operational FPR.
- يبقى `A_FAST` و`A_CONSENSUS` خطي المقارنة المرجعيين في P2-C. لا يُعاد إدخال Markov CUSUM أو Parallel Fusion ضمن المرشحين الجدد.

المرجع: [PR #48](https://github.com/uniqueteamyemen/CHAOS/pull/48) و[Workflow run #45487126771](https://github.com/uniqueteamyemen/CHAOS/actions/runs/45487126771).

### P2-C — دفعة الكواشف المستقلة

**[BENCH_ESTABLISHED — VALIDATION: PENDING]**

هذه هي المرحلة النشطة. تُنفّذ وفق وثيقة [P2-C Detector Batch Plan](docs/P2_C_DETECTOR_BATCH_PLAN_AR.md)، لا وفق فرع P2-B تجريبي سابق.

التصنيف الصحيح للمكونات:

- **FOCuS:** كاشف online بتقليم دالي functional pruning، مع prefix replay.
- **BOCPD:** كاشف Bayesian online؛ يجب أن يعتمد على posterior run-length mass وأن يحدد الاتجاه نسبةً إلى النظام السابق النشط.
- **Post-Quiet Huber:** كاشف sequential robust بعد أول 40 مشاهدة، ويُختبر بمقياسي المعايرة MAD وBartlett LRV.
- **Bartlett LRV:** مقدّر long-run variance / scale داخل مقارنة المعايرة، وليس detector مستقلاً ولا يصدر hits.
- **R-FPOP:** robust penalized segmentation بمسار منفصل. يجب الفصل بين `estimated_change_index` و`detection_index`; لا يدخل ترتيب online ما لم يثبت زمن إصدار سببي.

**تحديث موثق بعد PR #51 — 2026-11-25**

- دُمج PR #51 عند commit `86cb8e576dc0bd21044743dd2749f5bf1d8899ff`.
- اكتمل Synthetic Stress run `45524143985` وEconomic Competition run `45524159488` بنجاح على head `bd919d30613ff4612ca3924a613019ac20fceb22`.
- التغطية التي أثبتها التشغيل: 509 سلسلة (51 Pink Sheet و458 GEM)، منها 359 مؤهلة لـnull الشرطي ضمن تصميم P2-C.
- اجتازت بوابات التشغيل والتغطية وإعادة العرض السببي المسجلة في التقرير؛ هذا يثبت قابلية تنفيذ الـbenchmark وسلامة مساراته المحددة، ولا يثبت بعد صلاحية الكواشف إحصائياً أو اعتمادها تشغيلياً.
- يبقى قرار اعتماد P2-C العلمي **PENDING** إلى حين اكتمال التحقق المستقل وفق P1.4. لا يُرفع إلى VALIDATED بسبب نجاح CI وحده.

### P1.4 — Capability Operating Envelope

**[ACTIVE PHASE]**

العمل النشط هو بناء عقد تشغيلي قابل للفرض على مستوى runtime قبل أي Pilot موسع. نطاقه:

1. تثبيت cohort identities من أدلة الـmanifest؛ لا تُشتق قائمة C1 من العدد 147 وحده.
2. تنفيذ مسارين منفصلين: (أ) مطابقة هوية السلاسل أولاً، (ب) تدقيق معيار الإدراج في G1 بالتوازي. سجل الإغلاق يذكر 147 GEM لم تجتز G1، بينما G1 في الكود فحص مركب ADF + KPSS؛ لذلك لا يجوز تسمية القائمة «KPSS failures» أو «G1 failures» حتى توثيق سبب كل سجل.
3. حد زمني للتحقق: 24 ساعة من بدء المهمة. عند انقضائه، يسجل `C1_STATUS: PARTIALLY_VERIFIED` ويقتصر Pilot على الهويات المؤكدة فقط، مع استمرار تدقيق المعيار بالتوازي.
4. تسجيل `original_count_claimed`, `verified_count`, `discrepancy_reason`, و`discrepancy_severity`؛ أي فرق بين العدد المعلن والفعلي يبقى ظاهراً ولا يُسوّى لإجبار العدد على 147.
5. فصل Original Alarm Burden عن Synthetic Null FPR وInjection Recall وDetection Delay؛ احتساب احتمالية إنذار واحد أو أكثر لكل سلسلة من محاكاة null مباشرة، وعدم مساواة ARL0=500 بـP0≤0.10.
6. تثبيت معايير One-to-One matching لـR-FPOP، معايرة Bartlett عند مستوى مخاطر متساوٍ، مخرجات BOCPD posterior، الاتجاهين، MDE، التباين بين السلاسل، Shuffle Null، replay، وحالات PASS/FAIL/INCONCLUSIVE قبل أي كشف holdout.
7. لا تشغيل Pilot ثقيل في commit الخاص بالبروتوكول أو بحقن الاختبارات. يبدأ التشغيل في خطوة منفصلة صريحة وموسومة `[skip-p2-full]`.

يُنفذ كل تسليم في commit مستقل قابل للمراجعة على الفرع `feat/p1-4-capability-envelope-pilot-v1-20261125`. لا يجمع commit واحد تحديث الحالة والـcohorts والـschema والبروتوكول وحقن الاختبارات.

## نقطة البدء الإلزامية

اقرأ بالترتيب قبل أي تعديل:

1. [AGENTS.md](AGENTS.md) — قواعد النزاهة وحماية الأرشيف.
2. [CHAOS Execution Plan v2](docs/CHAOS_EXECUTION_PLAN_V2_AR.md) — الخطة المعمارية والتنفيذية العليا.
3. [P2-C Detector Batch Plan](docs/P2_C_DETECTOR_BATCH_PLAN_AR.md) — المرجع التاريخي للتنفيذ المقارن، مع حالة التحقق العلمي المفتوحة المبينة أعلاه.

## بوابات لا يجوز تجاوزها

- لا تعدّل `experiments/**` أو `structural_engine/isolated_break_detector_v1/**` في هذه الدفعة.
- لا تغيّر مخرجات P2-B المنشورة أو بيانات cohort المثبتة.
- لا تحذف أو تستبدل اختبارات موجودة في `p2_b_benchmark/tests/test_core.py`; أضف اختبارات P2-C فوقها مع إبقاء اختبارات الشرائح الأربع والتجميع وABSTAIN و`_score_all` وA_CONSENSUS prefix replay.
- يجب أن تكون أول 40 مشاهدة للمعايرة فقط، ويجب تسجيل `ABSTAIN` وسببه عند صفر/فساد scale أو عدم كفاية البيانات.
- يجب أن يمر كل online detector باختبارات prefix replay وfuture-suffix mutation.
- يجب أن يعرض R-FPOP موضع التغير المقدّر ووقت الكشف كحقلين منفصلين.
- يجب مقارنة Post-Quiet Huber + MAD مع Post-Quiet Huber + Bartlett LRV؛ لا تسجّل Bartlett كذراع كشف مستقل.
- لا PR ولا تشغيل على cohort الـ509 قبل اجتياز اختبارات الضغط الثمانية في خطة P2-C، والتحقق من حدود runtime والذاكرة، وتحديث `p2_b_benchmark/SHA256SUMS.txt` والتحقق من كل البصمات.
- لا دمج لمجرد نجاح CI؛ جودة الكشف والامتناع والتأخير والاتجاه وnull والـholdout بوابات مستقلة.

## حالة محاولة التنفيذ السابقة

أُغلق PR #49 دون دمج لأنه بُني قبل تطبيق تصنيف P2-C وبواباته، وحذف اختبارات قائمة واستعمل تمثيلات تقريبية لبعض الخوارزميات. لا تستخدم فرع `feat/p2b-five-detector-competition` بوصفه أساساً معتمداً أو مصدراً للنتائج. يعاد بناء الدفعة من `main-phase2` بعد تثبيت هذه المرجعية.

---

**قاعدة الحالة:** عند أي تعارض بين هذا الملف وملخص محادثة أو فرع غير مدمج، تُقرأ الملفات الحالية من `main-phase2` ويُحدّث هذا الملف بدليل وcommit محددين.


**فرع العمل الحالي:** `feat/p1-4-capability-envelope-pilot-v1-20261125` (مبني من `main-phase2@86cb8e5`).
