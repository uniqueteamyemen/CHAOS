# تقرير استكمال فجوات Data Readiness Gate

> **نطاق التنفيذ:** استُكملت الفجوات الثلاث المحددة فقط: **UCDP Country-Year v26.1**، ومجموعة صغيرة مبررة من **EIA annual series**، ومتغير بيئي شهري أصلي من **NOAA GSOM v1**. لم تُحوّل أي بيانات يومية أو حدثية إلى قيم سنوية، ولم تُطبّق أي log أو differencing أو normalization أو imputation أو source reconciliation. لم يُشغّل TFT أو structure-learning أو surrogate أو أي نموذج، ولم تُعدّل `market-intelligence-engine` أو architecture/gateway.

## 1. خلاصة تنفيذية

أصبح لدينا الآن امتداد موثق للطبقة التاريخية يضيف ثلاث وظائف مختلفة زمنياً ودلالياً. أضيف UCDP Country-Year كطبقة **سنوية country-year** جاهزة من المصدر نفسه، وأضيفت سلسلتان مفهومتان من EIA هما استهلاك الطاقة للفرد وكثافة استهلاك الطاقة بالنسبة إلى الناتج، مع اختيار دولة-سنة كامل للفترة 2000–2024 لكل سلسلة مختارة. كما أضيفت ملفات NOAA GSOM الأصلية الشهرية لعنصر `PRCP` في تسع محطات محددة مسبقاً؛ بقيت هذه الطبقة شهرية ومحطة-محطة، ولم تُدخل في الـannual panel.

النتيجة لا تعني أن المصفوفة متعددة المجالات أصبحت معتمدة للتجربة. أكبر قيدين باقين هما أن الربط المحافظ بالاسم بين UCDP وWDI أعاد **155 دولة فقط من أصل 199 اسماً في UCDP**، وأن GSOM الحالي يمثل تسع محطات لا مناخاً وطنياً أو عالمياً. لذلك أُنشئت مقارنة جديدة تفصل بين جاهزية الأعمدة وبين صلاحية الادعاء بأن كل المجالات قابلة للمقارنة في نفس المصفوفة.

## 2. ما تم اقتناؤه فعلياً

| الفجوة | الأصل/الإصدار | المدى والتواتر | الحجم والسجلات | الحالة | المسار المحلي |
|---|---|---|---:|---|---|
| الصراع السنوي | UCDP Country-Year on Organized Violence within Country Borders v26.1 | 1989–2025، سنوي country-year | 7,132 صفاً، 74 حقلاً، 199 country IDs/names؛ ZIP الخام 167,144 bytes، CSV المفكك 2,302,102 bytes | **منزّل ومفكك مع codebook** | `raw/ucdp/country_year261/` و`staged/ucdp/country_year261/` |
| الطاقة السنوية | EIA INTL، اختيار مفاهيمي من bulk المنزّل | 1980–2024 لكل سلسلة مختارة، سنوي | 378 سلسلة فريدة: 189 دولة لكل مفهوم؛ 9,450 قيمة أصلية للفترة 2000–2024 | **مستخرج من bulk محلي وفق قاعدة معلنة** | `gap_assets/EIA_SELECTED_SERIES_CATALOG.csv` و`gap_assets/EIA_SELECTED_ANNUAL_2000_2024_LONG.csv` |
| البيئة الشهرية | NOAA GSOM v1، عنصر `PRCP` | شهري، محطات محددة، كل ملف له مداه الأصلي | 9 ملفات، 4,933 station-month rows، إجمالي الملفات 1,658,524 bytes | **منزّل كـnative monthly files** | `raw/noaa/gsom_monthly/stations/` |

تستند طبقة UCDP إلى [مركز التنزيل الرسمي لـUCDP][1]، الذي يصف Country-Year بأنه تجميع على مستوى الدولة والسنة مبني على UCDP GED. وتستند طبقة GSOM إلى metadata الرسمية لـ[NOAA GSOM v1][2]، التي تحدد المنتج كملخص شهري عالمي محدث أسبوعياً، وتذكر عنصر precipitation وتوفر التنزيل المباشر وDOI `10.7289/V5QV3JJ5`.

## 3. UCDP Country-Year: المتغيرات القابلة للاستخدام والربط

يحتوي الملف على 74 حقلاً. الحقول المرشحة للـannual panel هي `sb_exist` و`sb_total_deaths_best` و`ns_exist` و`ns_total_deaths_best` و`os_exist` و`os_total_deaths_best`. هذه ليست متغيرات مستنتجة من أسماء الأخبار؛ إنها حقول مصدرية موثقة في codebook، وتمثل وجود العنف القائم على الدولة، أو غير القائم على الدولة، أو العنف أحادي الجانب، وتقديرات الوفيات الأفضل داخل حدود الدولة في سنة معينة.

| variable_id | التعريف المصدرّي | النوع/الوحدة | التغطية الأصلية | القيم المفقودة في المصدر |
|---|---|---|---|---:|
| `sb_exist` | وجود state-based organized violence داخل حدود الدولة في سنة؛ القيمة 1 عند وجوده | boolean 0/1 | 1989–2025، 7,132 country-year rows | 0 حقلاً مفقوداً في الملف |
| `sb_total_deaths_best` | أفضل تقدير لإجمالي وفيات state-based violence داخل حدود الدولة في سنة | integer fatalities | 1989–2025 | 0 حقلاً مفقوداً في الملف |
| `ns_exist` | وجود non-state violence داخل حدود الدولة في سنة | boolean 0/1 | 1989–2025 | 0 حقلاً مفقوداً في الملف |
| `ns_total_deaths_best` | أفضل تقدير لإجمالي وفيات non-state violence داخل حدود الدولة في سنة | integer fatalities | 1989–2025 | 0 حقلاً مفقوداً في الملف |
| `os_exist` | وجود one-sided violence داخل حدود الدولة في سنة | boolean 0/1 | 1989–2025 | 0 حقلاً مفقوداً في الملف |
| `os_total_deaths_best` | أفضل تقدير لإجمالي وفيات one-sided violence داخل حدود الدولة في سنة | integer fatalities | 1989–2025 | 0 حقلاً مفقوداً في الملف |

أُجري ربط محافظ بالاسم بعد التطبيع النصي وإزالة العلامات، مع اشتراط التطابق الفريد في WDI. النتيجة **155 تطابقاً فريداً من أصل 199 دولة/اسماً في UCDP**. نتج عن ذلك 3,783 صفاً UCDP قابلاً للربط مع دول panel المشتركة في الفترة 2000–2024. أما الأسماء غير المطابقة فلم تُربط بالتخمين؛ ملف `UCDP_COUNTRY_NAME_MAPPING_AUDIT.csv` يميز `exact-normalized-unique` عن `unmatched`. لذلك لا تمثل الخلايا الفارغة للـUCDP في panel غياب العنف بالضرورة؛ بعضها ناتج عن عدم اكتمال crosswalk، ويجب فصله لاحقاً عن missingness المصدرية.

## 4. EIA: لماذا اختيرت هذه المجموعة الصغيرة؟

لم تُستخدم نتيجة EIA البالغة 104,407 series كأنها مصفوفة واحدة. اختير مفهومان فقط لأن لهما دورين مختلفين وقابلين للتفسير: **استهلاك الطاقة للفرد** بوحدة `million Btu per person`، و**استهلاك الطاقة لكل الناتج** بوحدة `thousand Btu per USD at purchasing power parities`. الأول يصف مستوى استخدام الطاقة بالنسبة إلى السكان، والثاني يصف كثافة الطاقة بالنسبة إلى النشاط الاقتصادي. كلاهما بقي بوحدته الأصلية ولم يُعاد حسابه من WDI أو IMF.

كانت قاعدة الاختيار قابلة لإعادة الإنتاج: تواتر EIA يجب أن يكون `A`، و`geography` يجب أن يكون واحداً من 194 معرف دولة مشتركة في panel WDI×IMF، ويجب أن تحتوي السلسلة على قيمة غير فارغة لكل سنة من 2000 إلى 2024، وأن يطابق الاسم أحد المفهومين. نتج عن ذلك 189 دولة لكل مفهوم، أي 189/194 من دول panel لكل عمود EIA. الدول الخمس التي لم تحقق القاعدة بقيت مفقودة، ولم تُملأ.

| مفهوم EIA | عدد السلاسل الفريدة | true range | observed 2000–2024 لكل سلسلة | الوحدة |
|---|---:|---|---:|---|
| `energy_consumption_per_capita` | 189 | 1980–2024 | 25/25 | million Btu per person |
| `energy_consumption_per_gdp` | 189 | 1980–2024 | 25/25 | thousand Btu per USD at purchasing power parities |

هذا الاختيار لا يساوي اختيار مصدر ثالث مستقل لكل مفهوم؛ إنه subset من [EIA INTL bulk facility][3]، مع الاحتفاظ بـ`series_id` و`geography` و`last_updated` وmetadata الأصلية. ولذلك يجب إبقاء أعمدة EIA منفصلة عن أي متغير يشبهها في WDI أو IMF، وعدم المتوسط بينها.

## 5. NOAA GSOM: المتغير البيئي الشهري وحدوده

اختير عنصر `PRCP` فقط من ملفات GSOM التسعة: **إجمالي الهطول الشهري** كما يوزعه المنتج الأصلي. لم تُحوّل ملفات GHCN-Daily السابقة إلى شهري، بل نُزّلت ملفات GSOM monthly مباشرة من مسار NOAA. توضح [وثيقة GSOM الرسمية][2] أن المنتج شهري، يغطي من 1763 إلى الحاضر، ويضم precipitation وtemperature وعناصر أخرى، مع ملفات CSV وبيانات محطة محددة.

| station variable | true start | true end | مرصود 2000–2024 | المتوقع | التغطية |
|---|---|---|---:|---:|---:|
| `ASN00015590:PRCP` | 1941-11 | 2026-07 | 300 | 300 | 100.00% |
| `BRM00083208:PRCP` | 1989-01 | 2025-07 | 71 | 300 | 23.67% |
| `CF000064459:PRCP` | 1976-11 | 2020-09 | 3 | 300 | 1.00% |
| `GME00123190:PRCP` | 1986-04 | 2026-06 | 300 | 300 | 100.00% |
| `IN012141800:PRCP` | 1943-01 | 2024-07 | 42 | 300 | 14.00% |
| `IZ000040665:PRCP` | 1950-04 | 2025-11 | 26 | 300 | 8.67% |
| `JA000047770:PRCP` | 1951-01 | 2024-12 | 226 | 300 | 75.33% |
| `MY000048657:PRCP` | 1961-01 | 2025-07 | 262 | 300 | 87.33% |
| `USC00145852:PRCP` | 1962-08 | 2026-06 | 254 | 300 | 84.67% |

هذا الجدول يبين أن GSOM الحالي مناسب كـ**طبقة بيئية شهرية ذات نطاق محطة واضح**، وليس كعمود بيئي مشترك لكل 194 دولة. حتى المحطتان المكتملتان لا تمثلان متوسطاً وطنياً أو عالمياً. لذلك لم تدخل GSOM في أي annual candidate comparison، ولا توجد عملية annualization مخفية في الملفات أو الكود.

## 6. مصفوفة التغطية المحدثة

أُنشئ الملف `VARIABLE_LEVEL_COVERAGE_MATRIX_GAP_AUGMENTED.csv` بإضافة **481 سجلاً متغيرياً/حقلياً** إلى المصفوفة السابقة: 74 حقلاً من UCDP Country-Year، و378 series من EIA، و9 station-level PRCP fields من GSOM. أصبح عدد السجلات **105,026**. لكل سجل توجد حقول `source`, `variable_id`, `definition`, `unit`, `native_frequency`, `true_start_date`, `true_end_date`, `missing_gaps`, `definition_methodology_shifts`, و`provenance`.

| الطبقة | عدد سجلات المتغيرات/الحقول في المصفوفة المحدثة | ملاحظة التغطية |
|---|---:|---|
| WDI selected | 12 | entity-year coverage 2000–2024 كما في gate السابقة |
| IMF WEO current | 8 | entity-year coverage 2000–2024؛ current vintage/projection caveat محفوظ |
| IMF historical forecasts | 3 | Spring/Fall vintage dimension؛ لا collapse |
| EIA INTL bulk | 104,407 | series-by-series؛ تواتر mixed ولا common panel مفترض |
| EIA selected annual subset | 378 | 189 دولة × مفهومين، 25 قيمة أصلية لكل سلسلة |
| UCDP Country-Year | 74 | annual country-year؛ 7,132 source rows، 199 country IDs |
| NOAA GHCN-Daily selected | 40 | daily station fields، منفصلة |
| NOAA GSOM selected | 9 | monthly station PRCP، منفصلة |
| UCDP GED | 49 | daily/event، منفصلة |
| UCDP/PRIO | 28 | annual conflict-year، منفصلة |
| GDELT reduced | 17 | date-coded event archive، payload غير مفكوك |
| FRED | 2 | monthly CPI وdaily WTI، منفصلة |

## 7. مقارنة candidate matrices بعد سد الفجوات

المقارنة التالية سنوية فقط. أُضيفت أعمدة EIA السنوية وحقول UCDP السنوية بعد الربط المحافظ. أما GSOM PRCP فظل خارج المقارنة لأنه شهري ومحطة-محطة. لم تُعتبر القيم الصفرية في UCDP missing؛ الفراغ فقط هو missing، ولم يُعالج crosswalk غير المطابق كغياب مؤكد للحدث.

| candidate matrix | عدد المتغيرات | observed / expected cells | التغطية الخلوية | الدول المكتملة عبر 25 سنة | التفسير |
|---|---:|---:|---:|---:|---|
| `macro_with_levels_previous` | 9 | 42,510 / 43,650 | 97.39% | 142 | baseline قبل الفجوات الجديدة |
| `macro_plus_eia_energy` | 11 | 51,860 / 53,350 | 97.21% | 140 | إضافة الطاقة تقلل التغطية قليلاً بسبب 5 دول بلا سلاسل EIA المختارة |
| `macro_plus_ucdp_conflict` | 15 | 65,208 / 72,750 | 89.63% | 118 | القيد الرئيسي هو 155-name crosswalk المحافظ، لا missingness داخل UCDP نفسه |
| `macro_plus_eia_plus_ucdp` | 17 | 74,558 / 82,450 | 90.43% | 116 | أغنى annual candidate حالياً، لكن ليس الأعلى اكتمالاً |

المرشح الأكثر اكتمالاً ما زال `macro_with_levels_previous`. أما المرشح الأنسب إذا كان المطلوب أن تظهر الطاقة في النسخة السنوية فهو `macro_plus_eia_energy`، لأنه يضيف مجالاً حقيقياً بتغطية شبه مكتملة وبلا mapping اسمي إضافي. المرشح `macro_plus_eia_plus_ucdp` هو الأكثر تنوعاً من حيث الاقتصاد والطاقة والصراع، لكنه لا ينبغي أن يُعامل كنسخة مكتملة قبل مراجعة crosswalk UCDP البالغ 155 تطابقاً فقط، وقبل اتخاذ قرار صريح بشأن التعامل مع الدول التي لا يوجد لها تطابق محافظ.

## 8. ما يمكن ربطه وما لا يمكن ربطه الآن

يمكن ربط WDI وIMF وEIA في annual country-year candidate باستخدام 194 معرفاً مشتركاً، مع 189 دولة متاحة في كل مفهوم EIA. يمكن إضافة UCDP مباشرة إلى **155 دولة ذات crosswalk موثق** في هذه المرحلة، مع إبقاء بقية الدول في حالة `unmatched` بدلاً من تحويلها إلى صفر أو null دلالي. ويمكن استخدام حقول UCDP السنوية المصدرية دون إعادة تجميع GED.

لا يمكن إدخال GSOM الحالي في annual panel دون تحويل شهري إلى سنوي، وهو ممنوع في هذه المرحلة. كما لا يجوز تفسير المحطات التسع على أنها مناخ الدول أو العالم، ولا يجوز استخدام `PRCP` كمتغير مشترك لـ194 دولة. تبقى GSOM طبقة monthly environmental scope منفصلة.

## 9. قرار التوقف عند هذه النقطة

أُغلقت الفجوات الثلاث المطلوبة فقط. لا توجد حاجة إلى تنزيل NOAA GSOY الكامل، أو كامل GHCN، أو Comtrade bulk، أو ACLED، أو EM-DAT، أو NASA FIRMS في هذه الخطوة. الملفات المشتقة جاهزة للمراجعة واعتماد candidate matrix، لكن **لم يُعتمد أي مرشح لتشغيل التجربة**. الخطوة التالية، بعد اعتماد المستخدم، يجب أن تكون قراراً صريحاً حول: هل يبدأ الاختبار بـ`macro_plus_eia_energy` بوصفه annual candidate عالي الجاهزية، أم ينتظر إدخال UCDP بعد استكمال crosswalk الموثق؟ لا يُنفذ أي منهما تلقائياً.

## 10. الملفات الناتجة

| الملف | الوصف |
|---|---|
| `readiness_gate/VARIABLE_LEVEL_COVERAGE_MATRIX_GAP_AUGMENTED.csv` | المصفوفة المحدثة على مستوى المتغير/الحقل، 105,026 سجلاً. |
| `readiness_gate/ANNUAL_PANEL_RAW_WDI_IMF_UCDP_EIA_2000_2024.csv` | panel سنوي خام 4,850 صفاً؛ WDI وIMF وEIA وUCDP في أعمدة منفصلة؛ لا GSOM داخله. |
| `readiness_gate/CANDIDATE_MATRIX_COMPARISON_GAP_AUGMENTED.json` | الأرقام القابلة لإعادة التشغيل للمقارنة الجديدة. |
| `readiness_gate/UCDP_COUNTRY_YEAR_PROFILE_GAP_AUGMENTED.json` | profile UCDP والتطابق المحافظ. |
| `gap_assets/EIA_SELECTED_SERIES_CATALOG.csv` | كتالوج 378 سلسلة EIA مختارة مع IDs والوحدات والتواريخ. |
| `gap_assets/EIA_SELECTED_ANNUAL_2000_2024_LONG.csv` | القيم السنوية الأصلية المختارة، 9,450 صفاً long format. |
| `gap_assets/UCDP_COUNTRY_NAME_MAPPING_AUDIT.csv` | تدقيق crosswalk UCDP إلى WDI، مع unmatched محفوظة. |
| `gsom_monthly_profile.json` | profile ملفات GSOM التسعة والتغطية الأصلية. |
| `raw/ucdp/country_year261/` | ZIP وcodebook وchecksum لـUCDP Country-Year. |
| `raw/noaa/gsom_monthly/` | GSOM CSV الأصلية ووثيقة NOAA الرسمية وchecksum. |
| `HISTORICAL_DATASET_ACQUISITION_INVENTORY.csv` | جرد Catalog-First محدث، 24 صفاً. |

## References

[1]: https://ucdp.uu.se/downloads/ "UCDP Dataset Download Center — Country-Year v26.1"
[2]: https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00946 "NOAA/NCEI Global Summary of the Month (GSOM), Version 1"
[3]: https://www.eia.gov/opendata/index.php#bulk-downloads "U.S. EIA Open Data and Bulk Downloads"
[4]: https://data.imf.org/en/datasets/IMF.RES:WEO "IMF World Economic Outlook Data"
[5]: https://datatopics.worldbank.org/world-development-indicators/ "World Bank World Development Indicators"
