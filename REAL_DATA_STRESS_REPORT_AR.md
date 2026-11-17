# تقرير اختبار الضغط التاريخي — CHAOS P2.2

وقت التشغيل UTC: 2026-11-17T17:55:27.171133+00:00
Commit المصدر: 3d9674f83fad346ae962fba5b4bf6c8a5422f903
الفرع: main-phase2
الكاشف المجمد: BreakDetectorV1؛ لم تتغير معادلاته أو ثوابته.

## 1. ملخص الجلب والتأهيل

- سلاسل Pink Sheet الطويلة (>500 عائد شهري): 51.
- سلاسل GEM الشهرية الثانوية (≥87 مشاهدة): 0.
- أحزمة USGS المستعلم عنها: 5/5؛ سلاسل الزلازل المؤهلة: 10.
- إجمالي السلاسل التي وصلت إلى الكاشف: 61.
- اجتازت G1 (ADF وKPSS): 50.
- لم تجتز G1 وتجاوزت Bootstrap: 11.
- السلاسل المستبعدة: 20؛ أخطاء المصادر: 4.

## 2. G0 وG1 ومنهج Bootstrap

- G0: عدد النقاط وفق الفوج، تسلسل زمني متصل بلا ملء للفجوات، قيم منتهية، وMAD غير متدهور في نافذة الأساس الأولى.
- Pink Sheet: يتطلب 501 عائد شهري على الأقل، أي 502 سعراً موجباً متصلاً على الأقل.
- GEM وفواصل USGS: يتطلب كل فوج ثانوي 87 مشاهدة/فاصلاً على الأقل.
- G1: ADF يرفض جذر الوحدة (p < 0.05) وKPSS لا يرفض استقرار المستوى (p ≥ 0.05). هذا فحص أولي مزدوج وليس برهاناً على الاستقرارية الصارمة.
- Stationary Block-Bootstrap: 999 إعادة توليد لكل سلسلة اجتازت G1 فقط؛ متوسط طول الكتلة الشهري 12 شهراً، وللفواصل الزلزالية 25 فواصل.
- إذا فشل G1، لا تُحسب FPR من Bootstrap لتلك السلسلة؛ تظهر حالة التجاوز صراحة في JSON.
- Bootstrap للفواصل الزلزالية تشخيص تسلسلي مشروط فقط، ولا يحل محل null قائم على نماذج point-process أو مراجعة declustering واكتمال الكتالوج.

## 3. الإنذارات ومعدلها لكل عقد

| الوضع | السلاسل | G1 مؤهلة | الإنذارات البنيوية | إنذارات/عقد | غير مرتبطة بالمراسي/عقد | Bootstrap FPR | Wilson 95% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Fast | 61 | 50 | 225 | 0.8216 | 0.0175 | 8.96% | 8.72–9.22% |
| Markov CUSUM H=8.5 | 61 | 50 | 716 | 2.6144 | 0.2228 | 37.77% | 37.34–38.19% |
| Consensus | 61 | 50 | 76 | 0.2775 | 0.0000 | 2.12% | 2.00–2.25% |

Bootstrap FPR هنا هو نسبة عينات العدم المعاد توليدها التي أصدرت إنذاراً بنيوياً واحداً على الأقل، ويُحسب فقط للسلاسل التي اجتازت G1. أما الإنذارات غير المرتبطة بمراسي الصدمات فليست تلقائياً إيجابيات كاذبة علمياً؛ قد توجد تحولات حقيقية غير مدرجة في سجل المراسي. هذا المعدل يُعرض فقط للسلاسل الشهرية التي تنطبق عليها مراسي الاقتصاد الكلي، ولا تُقارن به السلاسل الزلزالية.

### التفصيل حسب فوج البيانات

| الفوج | الوضع | السلاسل | G1 مؤهلة | الإنذارات | إنذارات/عقد | Bootstrap FPR |
|---|---|---:|---:|---:|---:|---:|
| seismic_event_interarrival | Fast | 5 | 1 | 213 | 9.4718 | 60.06% |
| seismic_event_interarrival | Markov | 5 | 1 | 649 | 28.8601 | 99.90% |
| seismic_event_interarrival | Consensus | 5 | 1 | 74 | 3.2907 | 46.45% |
| seismic_monthly_counts | Fast | 5 | 1 | 5 | 0.2222 | 19.62% |
| seismic_monthly_counts | Markov | 5 | 1 | 5 | 0.2222 | 61.26% |
| seismic_monthly_counts | Consensus | 5 | 1 | 2 | 0.0889 | 7.61% |
| strict_long_monthly | Fast | 51 | 48 | 7 | 0.0306 | 7.68% |
| strict_long_monthly | Markov | 51 | 48 | 62 | 0.2709 | 35.98% |
| strict_long_monthly | Consensus | 51 | 48 | 0 | 0.0000 | 1.08% |

## 4. تشخيص سلاسل GEM

| المؤشر | الحالة | سجلات شهرية | سلاسل البلدان | المقبولة |
|---|---|---:|---:|---:|
| CPTOTSAXN | api_error | 0 | 0 | 0 |
| IPTOTSAKD | api_error | 0 | 0 | 0 |
| DXGSRMRCHSAXD | api_error | 0 | 0 | 0 |
| DXGSRMRCHNSKD | api_error | 0 | 0 | 0 |
- خطأ GEM CPTOTSAXN: GET failed https://api.worldbank.org/v2/country/all/indicator/CPTOTSAXN?source=15&format=json&per_page=20000&page=3&date=1990M01%3A2023M12: HTTP Error 502: Bad Gateway
- خطأ GEM IPTOTSAKD: GET failed https://api.worldbank.org/v2/country/all/indicator/IPTOTSAKD?source=15&format=json&per_page=20000&page=1&date=1990M01%3A2023M12: HTTP Error 502: Bad Gateway
- خطأ GEM DXGSRMRCHSAXD: GET failed https://api.worldbank.org/v2/country/all/indicator/DXGSRMRCHSAXD?source=15&format=json&per_page=20000&page=1&date=1990M01%3A2023M12: HTTP Error 502: Bad Gateway
- خطأ GEM DXGSRMRCHNSKD: GET failed https://api.worldbank.org/v2/country/all/indicator/DXGSRMRCHNSKD?source=15&format=json&per_page=20000&page=1&date=1990M01%3A2023M12: HTTP Error 502: Bad Gateway

## 5. مطابقة مراسي الصدمات التاريخية

المراسي الأربع محددة قبل تشغيل الكاشف. المطابقة فئوية وواحد لواحد ضمن ±12 شهراً، وتستخدم وقت الكشف الفعلي. المهلة الموجبة تعني أن الإشارة سبقت المرساة، والسالبة تعني كشفاً لاحقاً لا إنذاراً مبكراً.

| المرساة | الوضع | السلاسل المؤهلة | المطابقات | نسبة الالتقاط | قبل المرساة | نسبة السابق | نفس الشهر | بعد المرساة | وسيط lead (شهر) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GFC_2008 | Fast | 51 | 1 | 2.0% | 0 | 0.0% | 0 | 1 | -7.00 |
| GFC_2008 | Markov | 51 | 4 | 7.8% | 4 | 7.8% | 0 | 0 | 4.00 |
| GFC_2008 | Consensus | 51 | 0 | 0.0% | 0 | 0.0% | 0 | 0 | — |
| OIL_2014 | Fast | 6 | 0 | 0.0% | 0 | 0.0% | 0 | 0 | — |
| OIL_2014 | Markov | 6 | 1 | 16.7% | 0 | 0.0% | 0 | 1 | -1.00 |
| OIL_2014 | Consensus | 6 | 0 | 0.0% | 0 | 0.0% | 0 | 0 | — |
| COVID_2020 | Fast | 51 | 0 | 0.0% | 0 | 0.0% | 0 | 0 | — |
| COVID_2020 | Markov | 51 | 5 | 9.8% | 3 | 5.9% | 0 | 2 | 2.00 |
| COVID_2020 | Consensus | 51 | 0 | 0.0% | 0 | 0.0% | 0 | 0 | — |
| UKRAINE_2022 | Fast | 40 | 2 | 5.0% | 2 | 5.0% | 0 | 0 | 7.50 |
| UKRAINE_2022 | Markov | 40 | 1 | 2.5% | 0 | 0.0% | 0 | 1 | -1.00 |
| UKRAINE_2022 | Consensus | 40 | 0 | 0.0% | 0 | 0.0% | 0 | 0 | — |

هذه المراسي تواريخ سياقية عامة وليست ادعاءً بأن كل سلعة أو سلسلة تعرضت لصدمة في اليوم نفسه. المطابقة الزمنية لا تثبت السببية ولا تثبت أن الإشارة كانت متاحة في الزمن الحقيقي عند وقوع الحدث.

## 6. أحزمة USGS

| الحزام | الأحداث | أول حدث UTC | آخر حدث UTC |
|---|---:|---|---|
| Japan–Kuril–Kamchatka | 21691 | 1980-01-04T16:42:08.500000+00:00 | 2024-12-27T19:10:05.808000+00:00 |
| Sunda–Andaman | 45547 | 1980-01-01T01:24:37.200000+00:00 | 2024-12-31T22:32:02.906000+00:00 |
| Andes subduction | 18074 | 1980-01-01T14:46:19.200000+00:00 | 2024-12-31T23:13:20.048000+00:00 |
| Alaska–Aleutian | 6400 | 1980-01-06T19:51:02.900000+00:00 | 2024-12-25T21:39:29.258000+00:00 |
| Hellenic–Anatolian | 3019 | 1980-01-21T07:15:53.800000+00:00 | 2024-12-29T08:02:09.337000+00:00 |

تُفحص أحزمة USGS بتمثيل الفواصل الزمنية بين الأحداث بالأيام، وبتمثيل العد الشهري الثانوي. معدل الإنذار لكل عقد لسلاسل الفواصل يستخدم المدة الفعلية بين أول وآخر حدث. النوافذ الجغرافية مربعات استعلام تقريبية وليست حدوداً تكتونية دقيقة.

## 7. حدود الاستنتاج

1. CONFIRMED حكم داخلي وفق قواعد الكاشف، وليس تحققاً مستقلاً من صدمة اقتصادية أو تحول جيولوجي.
2. Detection Delay بعد بدء الصدمة مختلف عن Warning Lead قبل الصدمة؛ لا يجوز عرض الكشف اللاحق على أنه إنذار مبكر.
3. البيانات التاريخية المنقحة حالياً لا تثبت أن القيم ذاتها كانت متاحة للمستخدم في تاريخ الحدث؛ ذلك يتطلب نسخ point-in-time.
4. لا ينتج هذا التشغيل نموذج احتمال أو إنذاراً تشغيلياً أو توقعاً زلزالياً.
5. سجل الصدمات محدود بأربعة مراسٍ عامة؛ الإنذارات غير المرتبطة بهذه المراسي لا تُصنف آلياً كإنذارات كاذبة.
6. تغطية GEM المعلنة 1990–2023 تضعه في الفوج الثانوي ≥87 نقطة، وليس فوج Pink Sheet الصارم >500 نقطة.
7. لم تُعدّل ملفات experiments أو معادلات BreakDetectorV1 المجمدة.

## 8. أخطاء المصادر والاستبعادات
- World Bank GEM CPTOTSAXN: GET failed https://api.worldbank.org/v2/country/all/indicator/CPTOTSAXN?source=15&format=json&per_page=20000&page=3&date=1990M01%3A2023M12: HTTP Error 502: Bad Gateway
- World Bank GEM IPTOTSAKD: GET failed https://api.worldbank.org/v2/country/all/indicator/IPTOTSAKD?source=15&format=json&per_page=20000&page=1&date=1990M01%3A2023M12: HTTP Error 502: Bad Gateway
- World Bank GEM DXGSRMRCHSAXD: GET failed https://api.worldbank.org/v2/country/all/indicator/DXGSRMRCHSAXD?source=15&format=json&per_page=20000&page=1&date=1990M01%3A2023M12: HTTP Error 502: Bad Gateway
- World Bank GEM DXGSRMRCHNSKD: GET failed https://api.worldbank.org/v2/country/all/indicator/DXGSRMRCHNSKD?source=15&format=json&per_page=20000&page=1&date=1990M01%3A2023M12: HTTP Error 502: Bad Gateway

- عدد السلاسل المستبعدة: 20

## 9. سجل التدقيق
- Manifest: real_data_stress_pipeline/results/real_data_stress_manifest.json
- Normalized inputs: artifacts/real_data_stress/derived/normalized_detector_inputs.csv SHA-256 7937ee6775f3147683f2f50f3dfd57609e5b9bef5896144107a220043bd57b58
- Dependency inventory: real_data_stress_pipeline/results/dependency_manifest.json
- Checksums: real_data_stress_pipeline/results/SHA256SUMS.txt
- Raw source responses: ضمن GitHub Actions Artifact. Pink Sheet يبقى في الذاكرة فقط ما دامت شروط إعادة توزيع ملف XLSX غير محسومة.

حالة التشغيل: COMPLETED_WITH_SOURCE_WARNINGS
