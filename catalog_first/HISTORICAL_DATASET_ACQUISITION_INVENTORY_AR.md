# Historical Dataset Acquisition Inventory

> **حالة التقرير:** Catalog-First Historical Acquisition — نسخة موثقة من الأصول المحلية والكتالوجات التي تم التحقق منها حتى 26 أغسطس 2026. هذا التقرير ليس تجربة تحليلية، ولا يتضمن تشغيل surrogate جديداً أو تعديلاً للمعمارية أو لبوابات السلامة.

## 1. الخلاصة التنفيذية

أُعيد بناء الجرد من الملفات المحلية المتحققة، ويضم **22 مدخلاً**: **12 مدخلاً نُزّل فعلياً** و**10 مداخل متاحة ككتالوج أو مسار تنزيل ولم تُنزّل بعد**. التنزيلات الفعلية تشمل WDI bulk، وIMF WEO الحالي وتاريخ التنبؤات، وUCDP GED وUCDP/PRIO، وEIA INTL، وسلسلتي FRED، وmetadata ومحطات NOAA المختارة، وأرشيف GDELT reduced. أما Comtrade وALFRED وACLED وEM-DAT وNASA FIRMS وملفات NOAA الشهرية/السنوية العالمية وCountry-Year الإضافي من UCDP فما زالت مسارات متاحة أو مرشحة، وليست حالات غياب للبيانات.

النتيجة الحاسمة هي أن المشكلة لم تكن غياب datasets تاريخية جاهزة، بل أن الحملة الأولى استخدمت مسار probes ضيقاً. توجد الآن مادة حقيقية كافية للانتقال لاحقاً إلى مصفوفة سنوية متعددة المجالات، لكن لا ينبغي بناء المصفوفة أو تشغيلها قبل حسم قائمة المتغيرات وcoverage الفعلي لكل متغير. أفضل نقطة بداية هي **panel سنوي على مستوى الدولة/التجميع للفترة 2000–2024**، مبني من WDI مع IMF WEO وEIA INTL وطبقة صراعات سنوية من UCDP؛ أما GED وGHCN-Daily وGDELT فتظل طبقة أحداث/يومية منفصلة ولا تُدمج عشوائياً مع السنوي.

| المؤشر | الحالة المتحققة |
|---|---:|
| إجمالي مداخل الجرد | 22 |
| نُزّل فعلياً مع مسار محلي | 12 |
| catalog/downloadable ولم يُنزّل | 10 |
| إعادة تشغيل تجربة 10,000 surrogate في هذه المرحلة | لا |
| تعديل architecture أو scientific safety gates | لا |
| شراء مصدر مدفوع | لا |
| رفع إلى OneDrive | لا؛ لم يوجد موصل OneDrive متحقق |

## 2. ما الذي تم تنزيله فعلياً؟

الجدول التالي هو السجل التشغيلي الأساسي. الأحجام الخام هي أحجام الملفات الأصلية المحتفظ بها، والأحجام المرحلية هي أحجام الاستخراج أو النسخ التي يمكن إعادة بنائها؛ لا تُعامل المرحلة كبديل عن الخام. الأرقام مأخوذة من profiles المحلية، لا من تقدير تقريبي.

| المصدر / dataset | الإصدار والفترة والتواتر | المتغيرات / السجلات | الحجم الخام → المرحلي | حالة وموضع الحفظ | الدور المقترح |
|---|---|---:|---:|---|---|
| **World Bank WDI — WDI bulk CSV: WDICSV + WDISeries + WDICountry + WDIfootnote + country-series + series-time** | WDI archive downloaded 2026-08-25; current archive date in page metadata 2026-07-15<br>1960–2025<br>annual | 1,498 series metadata rows / 396,970 observation-table rows; 264 country/aggregate rows in WDICountry | 269.7 MiB → 189.3 MiB | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/worldbank/wdi/WDI_CSV.zip`<br>staged: `/home/ubuntu/market_intelligence_workspace/catalog_first/staged/worldbank/wdi_csv/WDICSV.csv`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/manifest.sha256.txt` | Primary annual country/aggregate economic-development panel; candidate variables include output, prices, population, trade, energy, environment and social indicators selected from metadata. |
| **World Bank WDI — WDI bulk Excel workbook mirror with metadata** | same WDI archive download as CSV<br>catalog-dependent; annual indicators, many series extend before 2000<br>annual | WDI workbook mirror; series count corresponds to WDI catalog / workbook sheets; not normalized to one row count | 77.9 MiB → 77.9 MiB | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/worldbank/wdi/WDI_EXCEL.zip`<br>staged: `/home/ubuntu/market_intelligence_workspace/catalog_first/staged/worldbank/wdi_excel/WDIEXCEL.xlsx`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/manifest.sha256.txt` | Metadata-preserving alternate representation and audit cross-check for selected WDI series; not a second independent source. |
| **IMF WEO — April 2026 WEO current-vintage workbook: Countries, Country Groups, Commodity Prices, Country Group Composition** | April 2026 current vintage; publication date 2026-04-14<br>1980–2031 in workbook; separate historical observations from projections<br>annual | Countries 8,668 rows; Country Groups 689; Commodity Prices 75; composition 626 / 10,058 rows across four sheets | 5.3 MiB → 5.3 MiB | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/imf/weo/WEOApr2026all.xlsx`<br>staged: `/home/ubuntu/market_intelligence_workspace/catalog_first/staged/imf/weo/WEOApr2026all.xlsx`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/manifest.sha256.txt` | Primary annual macroeconomic cross-check and source of macro/commodity roles; use historical years only in the first experiment. |
| **IMF WEO — Historical Forecasts workbook: ngdp_rpch, pcpi_pch, bca_gdp_bp6** | Updated April 14, 2026; Spring/Fall vintages since 1990<br>vintage columns 1990–2026; each vintage contains 2 historical + 6 forecast years<br>annual with Spring/Fall vintage dimensions | 3 variables × 8,844 country/economy rows per sheet / 26,532 sheet-rows across three sheets; 77 columns per sheet | 10.4 MiB → 10.4 MiB | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/imf/weo/WEOhistorical.xlsx`<br>staged: `/home/ubuntu/market_intelligence_workspace/catalog_first/staged/imf/weo/WEOhistorical.xlsx`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/manifest.sha256.txt` | Revision/vintage layer for leakage-aware replay and source-conflict measurement; not averaged into current WEO values. |
| **UCDP — UCDP Georeferenced Event Dataset (GED) Global** | v26.1<br>1989–2025<br>daily/geocoded event records | 49 / 417968 | 37.3 MiB → 261.3 MiB | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/ucdp/ged261-csv.zip`<br>staged: `/home/ubuntu/market_intelligence_workspace/catalog_first/staged/ucdp/ged261/GEDEvent_v26_1.csv`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/ucdp/sha256sums.txt` | Event layer for conflict onset/intensity/deaths, kept separate from annual macro panel; can be aggregated only through an explicit documented event-to-period transformation. |
| **UCDP/PRIO — UCDP/PRIO Armed Conflict Dataset** | v26.1<br>1946–2025<br>annual conflict-year | 28 / 2816 | 44.9 KiB → 506.9 KiB | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/ucdp/ucdp-prio-acd-261-csv.zip`<br>staged: `/home/ubuntu/market_intelligence_workspace/catalog_first/staged/ucdp/prio261/UcdpPrioConflict_v26_1.csv`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/ucdp/sha256sums.txt` | Best direct annual bridge for conflict presence/intensity against WDI/WEO/EIA annual panels. |
| **EIA — International Energy bulk API dataset (INTL)** | bulk manifest/current download; series last-updated timestamps include 2026-08-21<br>catalog envelope 1949–2026; individual series vary<br>A 100,459; M 2,159; Q 1,789 | 104407 / 105055 | 23.0 MiB → 122.8 MiB | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/eia/INTL.zip`<br>staged: `/home/ubuntu/market_intelligence_workspace/catalog_first/staged/eia/intl/INTL.txt`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/fred_eia_sha256sums.txt` | Energy/commodity and energy-intensity roles in annual panel; select series by explicit definition and coverage, preserving annual/monthly/quarterly frequency. |
| **FRED — CPIAUCSL — Consumer Price Index for All Urban Consumers: All Items** | download captured 2026-08-25; latest revised graph series<br>1947–2026<br>monthly | 1 / 955 | 17.3 KiB → — | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/fred/CPIAUCSL.csv`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/fred_eia_sha256sums.txt` | Monthly price/real-value alignment candidate and source-conflict comparator; not mixed into annual inference without a declared aggregation layer. |
| **FRED — DCOILWTICO — Crude Oil Prices: West Texas Intermediate (WTI) — Cushing, Oklahoma** | download captured 2026-08-25; latest revised graph series<br>1986–2026<br>daily | 1 / 10599 | 174.7 KiB → — | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/fred/DCOILWTICO.csv`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/fred_eia_sha256sums.txt` | Global commodity-price shock context; keep native daily timestamps and derive monthly/annual views explicitly. |
| **NOAA/NCEI GHCN-Daily — Station, inventory, country metadata and README** | GHCN-Daily v3.34 README; metadata captured 2026-08-25<br>station inventory spans multiple historical ranges; catalog only<br>station-level daily product metadata | 132,501 station records; 782,497 inventory rows / 132,501 lines stations; 782,497 lines inventory; 219 country lines | 45.2 MiB → — | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/noaa/ghcn_daily`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/noaa/ghcn_daily/sha256sums.txt` | Coverage selection and station provenance layer; prevents downloading all global stations before event/geography scope is chosen. |
| **NOAA/NCEI GHCN-Daily — Nine station CSV files selected across North America, South America, Europe, Africa, Middle East, South Asia, East Asia, Southeast Asia and Oceania** | station files accessed 2026-08-25; selection manifest is local<br>1941–2026 by station; every selected PRCP/TMAX/TMIN inventory window covers 2000–2025<br>daily | 9 stations; observed PRCP/TMAX/TMIN and station-specific additional fields / 181974 | 22.7 MiB → — | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/noaa/ghcn_daily/stations`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/noaa/ghcn_daily/stations/sha256sums.txt` | Small, explicit environmental station layer for a later daily/event experiment; not a global climate average and not directly joined to annual country panel yet. |
| **GDELT — GDELT 1.0 MASTERREDUCEDV2 reduced country-level event archive** | archive named 1979–2013<br>1979–2013<br>date-coded event archive; reduced country-level collapse | single tab-delimited archive; exact columns/records not profiled because archive remains compressed / not counted; one 6,581,409,407-byte extracted file | 1.01 GiB → — | downloaded<br>raw: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/gdelt/GDELT.MASTERREDUCEDV2.1979-2013.zip`<br>provenance: `/home/ubuntu/market_intelligence_workspace/catalog_first/raw/gdelt/sha256sums.txt` | Separate long-range event/context layer; use only with a predeclared event coding and streaming/partition plan. |

### 2.1 ملاحظات دقيقة على الأصول الكبيرة

**WDI** ليس أربع سلاسل فقط. ملف CSV الخام يحتوي جداول observation وcountry وseries وfootnote وغيرها؛ profile المحلي سجل 1,498 series metadata rows و396,970 observation-table rows، مع أعمدة سنوية 1960–2025. metadata يحفظ التعريف والوحدة والدورية والمصدر والقيود وLicense Type. توزيع الترخيص الذي تم فحصه محلياً هو 1,495 سلسلة `CC BY-4.0` وثلاث سلاسل `CC BY 3.0 IGO`، ولذلك لا يجوز اختزال كل السلاسل في عبارة ترخيص واحدة [1].

**IMF WEO** تم الحصول عليه بصيغتين مختلفتين وظيفياً. `WEOApr2026all.xlsx` هو current vintage يضم مؤشرات اقتصادية وسلعاً وتوقعات؛ أما `WEOhistorical.xlsx` فيضم ثلاثة متغيرات فقط عبر Spring/Fall vintages منذ 1990، ويجب الحفاظ على بُعد vintage وعدم دمج القيم. ملاحظات IMF المحلية تحذر من revisions وsplicing وstaff estimates، ومن اختلاف WEO عن مصادر رسمية أخرى؛ وهذا يجعل الملف مهماً لقياس revision/leakage، لا مصدراً ينبغي فرضه كحقيقة وحيدة [2].

**UCDP GED** هو سجل أحداث يومية جغرافية مع actors وsource fields وdate precision وdeath estimates، بينما **UCDP/PRIO** conflict-year dataset سنوي من 1946–2025. الأول لا يحل محل الثاني: GED مناسب لطبقة الحدث، وPRIO مناسب لجسر سنوي أولي. ينص مركز UCDP الرسمي على أن التنزيلات الحالية مجانية تحت `CC BY 4.0` مع codebooks وversion history [3].

**GDELT reduced** محفوظ خاماً مضغوطاً بحجم يقارب 1.09 GB مع checksum، ونجح اختبار سلامة ZIP. يحتوي الأرشيف على payload غير مضغوط يقارب 6.58 GB للفترة 1979–2013، لكنه **لم يُفك ولم يُحلل**. هذا قرار تخزين وتحكم في النطاق، لا فشل تنزيل. بيانات GDELT هي observations مشتقة من الأخبار؛ لا ينبغي تقديمها كقياس ممثل للمجتمع أو كحقيقة سببية [4].

**NOAA** انتقل من catalog-only إلى تنزيل فعلي محدود ومبرر: نُزّلت ملفات station/inventory/country/README، ثم اختيرت تسع محطات موزعة إقليمياً لأن PRCP/TMAX/TMIN لكل منها يغطي 2000–2025 وفق inventory. ملفات المحطات نفسها تحتفظ بالعناصر المرصودة والسمات؛ لم يتم تركيب TAVG ولم يحدث imputation. لم يتم تنزيل all-station TAR أو GSOM/GSOY الكامل [5].

## 3. ما وُجد ويمكن تنزيله لكنه لم يُنزّل بعد؟

| dataset / المسار | ما هو متاح | سبب عدم التنزيل الحالي | القيمة المحتملة |
|---|---|---|---|
| **NOAA/NCEI — Global Summary of the Month (GSOM) v1** | 1763–present; monthly; station-month summaries; exact file count depends on query | Not downloaded before station/phenomenon scope decision; global extraction would be unnecessary at this stage. | Preferred monthly environmental candidate if the first experiment is monthly and geography/event scope is fixed. |
| **NOAA/NCEI — Global Summary of the Year (GSOY) v1** | 1763–present; annual; station-year summaries; search exposed 86,045 files and 146 data types | Deferred pending explicit geographic/phenomenon scope; full result is large but feasible under hybrid storage. | Strong annual environmental bridge if station/country aggregation is specified before download. |
| **GDELT — GDELT 1/2 full Events, GKG, Mentions and BigQuery options** | 1979–present depending on product; daily/current feeds with historical archive conventions; very large; product-dependent | Full archives are too large for indiscriminate local download; requires streaming, partitioning or BigQuery scope. | Optional event/context source after the reduced archive and event semantics are explicitly scoped. |
| **UN Comtrade — Global merchandise trade by reporter, partner, product and flow** | historical annual and monthly coverage; exact span/product coverage query-dependent; annual and monthly; multi-dimensional reporter × partner × commodity × flow | Premium subscription required for bulk millions-of-records route; free route requires registration/key and careful pagination. | High-value trade-flow layer, but defer until a bounded reporter/partner/product scope and credentials are available. |
| **FRED/ALFRED — Vintage-date and real-time-period downloads for selected FRED series** | series-dependent; potentially decades; series-dependent; selected series only; not downloaded | No selected series/vintage scope was authorized in this acquisition pass; FRED current files were downloaded instead. | Essential leakage-control layer for replaying what was known at historical dates; should be selected before any predictive replay. |
| **UCDP — Country-Year Dataset on Organized Violence within Country Borders** | post-1989; current listing covers through 2025; annual country-year; catalog-listed; exact count not downloaded | Not downloaded yet because GED and PRIO were prioritized first; no access failure. | Potential clean annual conflict bridge to WDI/WEO/EIA; preferred over ad-hoc aggregation if its definitions fit the matrix. |
| **USGS — Earthquake Catalog API / query service** | query-defined historical event range; event timestamps; query-defined | No scoped historical earthquake extraction in this pass; earlier USGS probe was limited and not a catalog-first bulk asset. | Optional natural-hazard event layer after selecting geographic scope; separate from annual macro panel. |
| **ACLED — Armed Conflict Location & Event Data** | recent historical coverage varies by region and product; event-level; catalog-dependent | No account/API credentials and no purchase/registration action taken in this pass. | Potential event-layer complement to UCDP, but only after licensing and overlap/definition audit. |
| **EM-DAT — International Disaster Database** | historical disaster records; exact span/product query-dependent; event-level; catalog-dependent | No registration/credential action taken; no paid access purchased. | Potential disaster-event layer, subject to inclusion-criteria and reporting-bias audit. |
| **NASA FIRMS — Global active fire / thermal anomalies archive and API** | historical coverage depends on sensor/product; event/detection timestamps; catalog-dependent | No selected sensor/geography/date scope or MAP_KEY acquisition in this pass. | Potential environmental shock/event layer after deciding whether fire is relevant to selected regions and period. |

### 3.1 العوائق مصنفة بدقة

| الحالة | التفسير الصحيح |
|---|---|
| **Comtrade** | قاعدة التجارة موجودة ومهمة، لكن bulk لملايين السجلات يتطلب اشتراكاً premium وفق صفحة الوصول الحالية؛ المسار المجاني bounded API/preview يحتاج registration/key وحدود pagination. لم يُشترَ شيء، ولا يصح وصف ذلك بأنه غياب للبيانات [6]. |
| **FRED/ALFRED** | فشل مسار FRED-MD المباشر السابق كان HTTP 403 لمسار محدد، وليس غياب FRED. تنزيلات FRED series-level نجحت. ALFRED متاح لتنزيل vintage/real-time، لكن يجب أولاً تحديد series وvintage المطلوبين؛ لا يجوز اعتبار latest FRED ملفاً تاريخياً لما كان معروفاً وقتها [7][8]. |
| **NOAA GSOM/GSOY** | الكتالوج والتنزيل الرسميان متاحان. تم تأجيل GSOM/GSOY الكاملين لأن التجربة الأولى لم تحدد بعد station/phenomenon/geography scope؛ تنزيل كل الملفات لمجرد توفرها يخالف سياسة التخزين الذكي. |
| **GDELT full / BigQuery** | المصدر مفتوح، لكن full Events/GKG كبير جداً؛ reduced archive وحده نُزّل. المسار الصحيح لاحقاً هو streaming/partition/query، لا فك كل الأرشيف محلياً بلا خطة [4]. |
| **ACLED وEM-DAT** | الكتالوجان موجودان، لكن الوصول يتطلب حساباً/شروط استخدام أو registration بحسب المنتج. لم تُستخدم credentials غير موجودة، ولم يُشترَ مصدر. هذه access/terms gates وليست نتائج سلبية عن جودة البيانات [9][10]. |
| **NASA FIRMS** | مسار التنزيل/API متاح، لكن لا توجد بعد مواصفة sensor/date/geography أو MAP_KEY مختارة؛ لذلك لم يُسحب أرشيف حرائق عالمي بلا نطاق [11]. |
| **USGS** | catalog/API query متاح للأحداث الزلزالية؛ لم يُنزّل bulk لأن الاستعلام الجغرافي والزمني يجب أن يحدد أولاً. probes السابقة لا تعني أن catalog غير متاح [12]. |
| **OneDrive** | فُحصت الإعدادات وقائمة الموصلات ولم يظهر موصل OneDrive متاحاً. لذلك لم يتم رفع أي ملف ولم تُفترض صلاحية غير متحققة. |

## 4. الترشيح العملي لأول مصفوفة حقيقية متعددة المجالات

### الترشيح الأساسي: panel سنوي country-year/aggregate للفترة 2000–2024

هذه ليست تجربة منفذة بعد، بل **مواصفة اختيار** قبل التجربة. الفترة 2000–2024 تعطي 25 سنة تقويمية مكتملة تقريباً وتتفادى إدخال سنة 2025 التي قد تكون غير مكتملة أو قابلة للمراجعة في بعض المصادر. يجب أولاً اختيار الدول/التجمعات التي تظهر فعلياً في المتغيرات المختارة؛ لا يُنشأ قاموس كيانات شامل لمجرد وجود دول في metadata.

| طبقة | dataset المرشح | ما الذي يدخل مبدئياً | ضابط الاستخدام |
|---|---|---|---|
| اقتصاد وتنمية | WDI bulk CSV | عدد صغير من السلاسل ذات تعريف ووحدة وتغطية واضحة: ناتج/نشاط، أسعار أو قوة شرائية، تجارة، طاقة/بيئة، وسكان أو بنية اجتماعية عند الحاجة | اختيار variable-level لا topic-level؛ الاحتفاظ بالقيم الخام والمصدر والقيود وعدم ملء الفجوات |
| اقتصاد كلي ومراجعات | IMF WEO April 2026 + WEO Historical Forecasts | مؤشرات النمو والتضخم والحساب الجاري/المالية أو السلع، مع current-vintage منفصل عن vintage replay | لا averaging مع WDI؛ WEO historical يستخدم للـvintage/leakage/revision، لا كقيمة بديلة تلقائية |
| طاقة | EIA INTL | سلاسل سنوية مختارة ذات تغطية 2000–2024 وتعريف صريح، مثل استهلاك الطاقة/الناتج أو إنتاج/استهلاك طاقة حسب النطاق | لا تستخدم envelope 104,407 series كأنها مصفوفة مكتملة؛ profile لكل series ثم coverage matrix |
| صراع/عنف منظم | UCDP Country-Year v26.1، مع UCDP/PRIO المتاح كمرجع | متغيرات country-year منظمة العنف، أو conflict-year presence/intensity حيث يناسب التعريف | يفضّل تنزيل Country-Year الرسمي قبل بناء aggregation يدوي من GED؛ GED يبقى منفصلاً |
| سوق/سلعة عالمية | FRED DCOILWTICO، وربما CPIAUCSL كمرجع شهري | سياق سلعي/سعري عالمي، لا كبديل عن EIA أو WDI | يحافظ على daily/monthly native frequency؛ السنوي derived فقط في alignment layer معلنة |
| متغير بيئي | لا يُفرض في المصفوفة السنوية قبل الاختيار | إمّا GSOM/GSOY محدد النطاق أو WDI climate/environment series ذات coverage مناسب | لا تنزيل GSOY/GSOM العالمي ولا z-score عالمي قبل تحديد الظاهرة وbaseline |

### قائمة WDI المرشحة للفحص قبل بناء المصفوفة

هذه الأكواد ليست DAGاً مفروضاً ولا متغيرات نهائية؛ إنها shortlist metadata يجب فحص coverage الفعلي لها على مستوى الدولة/السنة قبل أي اختبار: `NY.GDP.MKTP.KD` (GDP constant 2015 US$)، `NY.GDP.MKTP.KD.ZG` (GDP growth)، `NY.GDP.PCAP.KD` (GDP per capita)، `FP.CPI.TOTL.ZG` (CPI inflation)، `PA.NUS.PPP` (PPP conversion factor)، `NE.EXP.GNFS.KD.ZG` و`NE.IMP.GNFS.KD.ZG` (exports/imports growth)، `EG.USE.PCAP.KG.OE` (energy use per capita)، `AG.LND.PRCP.MM` (average precipitation)، `EN.ATM.CO2E.PC` إذا كانت تغطيته مناسبة، `SP.POP.TOTL` (population)، و`SL.UEM.TOTL.ZS` (unemployment). القائمة الآلية الكاملة وحقول الوحدة والمصدر والترخيص محفوظة في `FIRST_MATRIX_CANDIDATES.json`؛ لم تُستخدم لإنتاج نتائج سببية.

النتيجة العملية: **أولوية الاقتناء التالية ليست GDELT الكامل ولا all-station NOAA ولا Comtrade premium، بل UCDP Country-Year v26.1، ثم اختيار وفهرسة مجموعة صغيرة من EIA annual series، ثم تحديد طبقة بيئية سنوية أو شهرية ذات نطاق واضح.** بعد ذلك فقط تُبنى coverage matrix على مستوى المتغير، ويُقرر إن كانت المصفوفة السنوية غنية بما يكفي للتجربة.

### المسار البديل المنفصل: تجربة أحداث يومية/بيئية

يمكن لاحقاً تصميم طبقة مستقلة من UCDP GED + محطات GHCN-Daily المختارة + USGS أو FIRMS + جزء محدد من GDELT. هذه التجربة لا ينبغي أن تُدمج مباشرة مع panel السنوي؛ لأن event timestamps، ودقة التاريخ، وmissingness، ومعنى الخبر أو الحدث تختلف جذرياً عن القياسات السنوية. أي تحويل إلى شهر/سنة يجب أن يكون اشتقاقاً معلناً يحفظ الأصل، وليس استبدالاً للبيانات الأصلية.

## 5. قواعد الحوكمة التي بقيت نافذة

يبقى الخام immutable مع checksum ووقت الوصول ونسخة المصدر. تبقى الطبقات المرحلية قابلة للحذف وإعادة البناء ولا تُعامل كمصدر أصلي. لا يوجد forward-fill أو back-fill أو interpolation شامل، ولا متوسط قسري بين WDI وIMF وEIA وFRED. تُحفظ التناقضات كـsource contrasts، ويُسجل لكل اشتقاق source references والتحويل والتواتر والتسرب الزمني المحتمل.

الزمن هنا قيد ترتيب ومكوّن في اختبار precedence أو information flow، وليس برهاناً على السببية. أي candidate structural pattern يجب أن يمر لاحقاً عبر تصحيح تعدد الاختبارات، اختبار خارج العينة زمني، اختبار استقرار، وسجل rejected مستقل. لم تتغير هذه البوابات ولم يُعاد تشغيل baseline الحالي ذي 36 edge-lag و0 validated و36 rejected.

## 6. الملفات الناتجة ومواقعها

| الملف | الغرض |
|---|---|
| `/home/ubuntu/market_intelligence_workspace/catalog_first/HISTORICAL_DATASET_ACQUISITION_INVENTORY.csv` | CSV الآلي الكامل، 22 مدخلاً، مناسب للقراءة البرمجية والفرز حسب المصدر أو حالة التنزيل. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/HISTORICAL_DATASET_ACQUISITION_INVENTORY_AR.md` | هذا التقرير العربي التفصيلي. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/workbook_profile.json` | profile WDI وIMF الحالي والتاريخي. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/ucdp_profile.json` | profile GED وPRIO. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/eia_intl_profile.json` | profile EIA INTL. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/fred_eia_profile.json` | profile FRED/EIA raw assets. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/noaa_station_profile.json` | profile المحطات التسع المنزلة. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/FIRST_MATRIX_CANDIDATES.json` | shortlist آلي للمرشحين من WDI وEIA؛ catalog metadata فقط. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/official_source_notes_2026-08-26.md` | سجل الصفحات الرسمية التي تم فحصها وروابطها. |

## المراجع الرسمية

[1]: https://datatopics.worldbank.org/world-development-indicators/ "World Bank — World Development Indicators"
[2]: https://data.imf.org/en/datasets/IMF.RES:WEO "IMF Data — World Economic Outlook"
[3]: https://ucdp.uu.se/downloads/ "UCDP Dataset Download Center"
[4]: https://www.gdeltproject.org/data.html "GDELT — Data"
[5]: https://www.ncei.noaa.gov/access "NOAA NCEI — Data Access"
[6]: https://comtradeplus.un.org/ "UN Comtrade Plus"
[7]: https://fred.stlouisfed.org/series/CPIAUCSL "FRED — CPIAUCSL"
[8]: https://alfred.stlouisfed.org/help/downloaddata "ALFRED — Download Data Help"
[9]: https://acleddata.com/ "ACLED — Armed Conflict Location & Event Data"
[10]: https://www.emdat.be/ "EM-DAT — The International Disaster Database"
[11]: https://firms.modaps.eosdis.nasa.gov/ "NASA FIRMS"
[12]: https://earthquake.usgs.gov/fdsnws/event/1/ "USGS FDSN Earthquake Event Web Service"
