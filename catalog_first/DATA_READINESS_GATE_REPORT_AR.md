# Data Readiness Gate — Variable-Level Historical Coverage

> **نطاق هذا التقرير:** هذه بوابة جاهزية بيانات فقط. تم فحص الأصول الحقيقية المنزلة، واستخراج خصائص المتغيرات والتغطية، وبناء نسخة panel خام WDI/IMF للفترة 2000–2024. لم يتم تشغيل TFT أو structure-learning أو surrogate، ولم تُطبق log/return/differencing/normalization/imputation، ولم تُعدّل `market-intelligence-engine` أو أي بوابة معمارية.

## 1. القرار الحالي

البيانات **جاهزة لبناء candidate matrices موصوفة**، لكنها ليست معتمدة بعد لتشغيل تجربة. توجد 194 دولة/اقتصاداً في التقاطع الاسمي بين WDI وIMF للمتغيرات المختارة، و4,850 صفاً في panel الخام (194 × 25 سنة). يحتوي panel على 20 عمود قيمة منفصلاً: 12 من WDI و8 من IMF؛ من أصل 97,000 خلية قيمة متوقعة، توجد 87,728 خلية غير فارغة و9,272 خلية مفقودة. هذا يعني أن التقاطع لا يساوي اكتمالاً؛ القيم المفقودة بقيت فارغة ولم تُعالج.

من ناحية الدولة، أعاد فحص metadata أن **كل الـ194 معرفاً مشتركاً تقع ضمن الدول ذات Region غير فارغ في WDI**؛ لم تُدخل تجمعات إقليمية بسبب وجودها في القاموس. ومع ذلك، أسماء WDI وIMF محفوظة في أعمدة منفصلة، لأن اختلاف تسمية الكيان نفسه جزء من provenance لا يُحل بالتخمين.

| فحص البوابة | النتيجة |
|---|---:|
| فترة panel الخام | 2000–2024 (25 سنة) |
| دول/اقتصادات WDI ذات أي متغير مختار | 264 |
| دول/اقتصادات IMF ذات أي متغير مختار | 197 |
| التقاطع الجغرافي الفعلي بين المصدرين | 194 |
| صفوف panel الخام | 4850 |
| أعمدة WDI/IMF الخام | 20 (12 WDI + 8 IMF) |
| خلايا قيمة غير فارغة | 87,728 / 97,000 (90.44%) |
| كيانات مكتملة لكل متغيرات WDI الـ12 عبر 25 سنة | 148 |
| كيانات مكتملة لكل متغيرات IMF الـ8 عبر 25 سنة | 111 |
| كيانات مكتملة لكل الـ20 متغيراً معاً | 98 |
| تجربة أو تدريب نموذج | لم يُنفذ |
| تحويلات أو imputation أو reconciliation | لم تُنفذ |

## 2. الأصول الـ12 المنزلة فعلياً وما يمكن استخدامه منها

المقصود بالـ12 هنا هو الأصول/التنزيلات التي سُجلت في جرد Catalog-First السابق، لا أن كل أصل يساوي متغيراً سنوياً صالحاً. بعض الأصول عبارة عن metadata أو archive خام أو طبقة أحداث، ولذلك لا تدخل panel السنوي مباشرة.

| الأصل المنزّل | التغطية الأصلية | المتغيرات/السجلات | ما هو صالح الآن | الفصل الزمني |
|---|---|---:|---|---|
| WDI bulk CSV | 1960–2025، سنوي | 1,498 series metadata؛ 396,970 observation rows | 12 متغيراً مرشحاً فُحصت خلوياً هنا، ويمكن اختيار subset منها | annual |
| WDI bulk Excel | نفس archive، سنوي | workbook mirror + metadata | audit/metadata representation، وليس مصدراً مستقلاً ثانياً | annual |
| IMF WEO April 2026 current | 1980–2031 في workbook؛ actual/current مفصول عن projections | Countries 8,668 rows؛ Country Groups 689؛ Commodities 75 | 8 مؤشرات WEO مرشحة مع UNIT/Description وcoverage 2000–2024 | annual |
| IMF WEO Historical Forecasts | Spring/Fall vintages منذ 1990؛ 2 historical + 6 forecast لكل vintage | 3 sheets × 8,844 rows | revision/vintage/leakage layer؛ ليست قيمة بديلة تلقائية | annual + vintage |
| UCDP GED Global v26.1 | 1989–2025 | 417,968 event rows × 49 fields | أحداث عنف منظم، source/date/geography/death fields | daily/event |
| UCDP/PRIO Armed Conflict v26.1 | 1946–2025 | 2,816 conflict-year rows × 28 fields | conflict-year context، لكنه ليس panel مستخدماً هنا بعد | event-derived annual conflict-year |
| EIA INTL bulk | series-specific؛ envelope 1949–2026 | 104,407 series objects + 232 categories؛ 100,459 annual / 2,159 monthly / 1,789 quarterly | متغيرات طاقة/اقتصاد تُختار series-by-series بعد فحص coverage | mixed native |
| FRED CPIAUCSL | 1947–2026 | 955 monthly observations | CPI index؛ يبقى monthly ولا يدخل annual panel دون alignment معلن | monthly |
| FRED DCOILWTICO | 1986–2026 | 10,599 daily observations | WTI spot price؛ يبقى daily ولا يُحوّل هنا | daily/business-day |
| NOAA GHCN-Daily metadata + 9 station files | metadata متعدد المدى؛ المحطات المختارة تغطي PRCP/TMAX/TMIN نافذة 2000–2025 | metadata + 9 ملفات؛ 181,983 station rows تقريباً؛ per-element fields | قياسات محطة يومية مع flags/attributes؛ ليست متوسطاً عالمياً | daily |
| GDELT reduced raw archive | 1979–2013 | 17 header fields؛ payload غير مفكوك 6.58 GB | archive/event context فقط؛ لم يُعدّ عدد الصفوف | date-coded event archive |

الأصلان الأكثر مباشرة لبناء panel دولة-سنة هما **WDI CSV** و**IMF WEO current**. UCDP PRIO وEIA INTL يمكن أن يضيفا مجال الصراع والطاقة لاحقاً بعد اختيار نسخة/متغيرات محددة. أما GED وGDELT وFRED وNOAA اليومية فهي بيانات حقيقية قابلة للاستخدام، لكن في طبقات مختلفة زمنياً ودلالياً ولا يجوز إدخالها في annual matrix بمجرد تجميعها.

## 3. تحقق `FIRST_MATRIX_CANDIDATES.json` والمتغيرات الأساسية

الملف يعلن صراحةً أنه `candidate catalog only; no experiment run` ويستهدف `2000–2024 annual primary panel`. يحتوي على **12 أكواد WDI** ونتيجة بحث metadata مقدارها 54,504 series مطابقة في EIA، لكن الرقم الأخير ليس عدد متغيرات معتمدة؛ إنه عدد matches نصية يحتاج إلى تقليص series-by-series.

| الدور | variable_id | التعريف/الوحدة كما ظهرت في metadata | المصدر الأصلي داخل WDI metadata |
|---|---|---|---|
| energy_environment | `AG.LND.PRCP.MM` | Average precipitation in depth (mm per year)<br>millimeter (mm) per year | FAOSTAT, Food and Agriculture Organization of the United Nations (FAO), publisher: Food and Agriculture Organization of the United Nations (FAO) |
| trade_flows | `EG.USE.PCAP.KG.OE` | Energy use (kg of oil equivalent per capita)<br>kg of oil equivalent per capita | IEA Energy Statistics Data Browser, International Energy Agency (IEA), uri: https://www.iea.org/data-and-statistics/data-tools/energy-statistics-data-browser, publisher: International Energy Agency (IEA), date accessed: 2025-03-25 |
| prices_purchasing_power | `FP.CPI.TOTL.ZG` | Inflation, consumer prices (annual % growth)<br>% | International Financial Statistics database, International Monetary Fund (IMF) |
| trade_flows | `NE.EXP.GNFS.KD.ZG` | Exports of goods and services (annual % growth)<br>% | Country official statistics, National Statistical Organizations and/or Central Banks; National Accounts data files, Organisation for Economic Co-operation and Development (OECD); Staff estimates, World Bank (WB) |
| trade_flows | `NE.IMP.GNFS.KD.ZG` | Imports of goods and services (annual % growth)<br>% | Country official statistics, National Statistical Offices (NSOs); National Accounts data files, Central Banks; Staff estimates, World Bank (WB) |
| output_activity | `NY.GDP.MKTP.CD` | GDP (current US$)<br>current US$ | Country official statistics, National Statistical Organizations and/or Central Banks; National Accounts data files, Organisation for Economic Co-operation and Development (OECD); Staff estimates, World Bank (WB) |
| output_activity | `NY.GDP.MKTP.KD` | GDP (constant 2015 US$)<br>constant 2015 US$ | Country official statistics, National Statistical Organizations and/or Central Banks; National Accounts data files, Organisation for Economic Co-operation and Development (OECD); Staff estimates, World Bank (WB) |
| output_activity | `NY.GDP.MKTP.KD.ZG` | GDP (annual % growth)<br>% | Country official statistics, National Statistical Organizations and/or Central Banks; National Accounts data files, Organisation for Economic Co-operation and Development (OECD); Staff estimates, World Bank (WB) |
| output_activity | `NY.GDP.PCAP.KD` | GDP per capita (constant 2015 US$)<br>constant 2015 US$ | Country official statistics, National Statistical Organizations and/or Central Banks; National Accounts data files, Organisation for Economic Co-operation and Development (OECD); Staff estimates, World Bank (WB) |
| output_activity | `PA.NUS.PPP` | PPP conversion factor, GDP (LCU per international $)<br>Local currency unit per international dollar | International Comparison Program (ICP), World Bank (WB), uri: https://www.worldbank.org/en/programs/icp/data, publisher: International Comparison Program, type: International statistical program, date accessed: May 30, 2024, date published: May 30, 2024; The Eurostat PPP Programme, Eurostat (ESTAT), uri: https://ec.europa.eu/eurostat/databrowser/explore/all/all_themes, publisher: Eurostat, type: International statistical program; The OECD PPP Programme, Organisation for Economic Co-operation and Development (OECD), uri: https://data-https://data-explorer.oecd.org/, publisher: OECD |
| population_social | `SL.UEM.TOTL.ZS` | Unemployment, total (% of total labor force) (modeled ILO estimate)<br>% of total labor force | ILO Modelled Estimates database (ILOEST), International Labour Organization (ILO), uri: https://ilostat.ilo.org/data/bulk/, publisher: ILOSTAT, type: external database, date accessed: January 17, 2026 |
| population_social | `SP.POP.TOTL` | Population, total<br>Unit | World Population Prospects, United Nations (UN), uri: https://population.un.org/wpp/, publisher: UN Population Division; Statistical databases and publications from national statistical offices, National Statistical Offices (NSOs), uri: https://unstats.un.org/home/nso_sites/, publisher: National Statistical Offices; Eurostat: Demographic Statistics, Eurostat (ESTAT), uri: https://ec.europa.eu/eurostat/data/database?node_code=earn_ses_monthly, publisher: Eurostat; Population and Vital Statistics Report (various years), United Nations (UN), uri: https://unstats.un.org, publisher: UN Statistics Division |

الملاحظة المهمة هي أن `FIRST_MATRIX_CANDIDATES.json` صنّف بعض المتغيرات تصنيفاً موضوعياً غير دقيق: `EG.USE.PCAP.KG.OE` ظهر تحت `trade_flows` رغم أن تعريفه طاقة، وبعض المصدر/الوحدة حقولها فارغة في WEO. لذلك استُخدم الملف كبداية فهرسة، لا كقرار نهائي. التغطية الفعلية أدناه هي المرجع التشغيلي الأقوى.

## 4. Variable-Level Coverage Matrix — المتغيرات السنوية المرشحة

تم إنشاء `VARIABLE_LEVEL_COVERAGE_MATRIX.csv` بسجل مستقل لكل متغير/field. بالنسبة لـWDI وIMF حُسبت الخلايا المرصودة في 2000–2024 على أساس entity-year، مع الاحتفاظ بالتاريخ الأصلي الأوسع. بالنسبة لـEIA حُفظت كل سلسلة لها data array في السجل مع start/end/frequency/unit/geo؛ وبالنسبة للأحداث والمحطات سُجلت تغطية الحقل وعدد القيم غير الفارغة، من دون اختراع annual coverage لها.

### 4.1 WDI — 12 متغيراً على مستوى الدولة/السنة

| variable_id | التعريف والوحدة | true start–end | الدول النشطة | observed / expected 2000–2024 | coverage | دول مكتملة 25 سنة |
|---|---|---|---:|---:|---:|---:|
| `AG.LND.PRCP.MM` | Average precipitation in depth (mm per year)<br>millimeter (mm) per year | 1961–2022 | 182 | 4160/4550 | 91.43% | 0 |
| `EG.USE.PCAP.KG.OE` | Energy use (kg of oil equivalent per capita)<br>kg of oil equivalent per capita | 1990–2024 | 225 | 4785/5625 | 85.07% | 51 |
| `FP.CPI.TOTL.ZG` | Inflation, consumer prices (annual % growth)<br>% | 1960–2025 | 240 | 5694/6000 | 94.90% | 199 |
| `NE.EXP.GNFS.KD.ZG` | Exports of goods and services (annual % growth)<br>% | 1961–2025 | 212 | 4823/5300 | 91.00% | 151 |
| `NE.IMP.GNFS.KD.ZG` | Imports of goods and services (annual % growth)<br>% | 1961–2025 | 214 | 4875/5350 | 91.12% | 153 |
| `NY.GDP.MKTP.CD` | GDP (current US$)<br>current US$ | 1960–2025 | 261 | 6417/6525 | 98.34% | 243 |
| `NY.GDP.MKTP.KD` | GDP (constant 2015 US$)<br>constant 2015 US$ | 1960–2025 | 260 | 6334/6500 | 97.45% | 240 |
| `NY.GDP.MKTP.KD.ZG` | GDP (annual % growth)<br>% | 1961–2025 | 261 | 6343/6525 | 97.21% | 238 |
| `NY.GDP.PCAP.KD` | GDP per capita (constant 2015 US$)<br>constant 2015 US$ | 1960–2025 | 260 | 6334/6500 | 97.45% | 240 |
| `PA.NUS.PPP` | PPP conversion factor, GDP (LCU per international $)<br>Local currency unit per international dollar | 1990–2025 | 205 | 4968/5125 | 96.94% | 189 |
| `SL.UEM.TOTL.ZS` | Unemployment, total (% of total labor force) (modeled ILO estimate)<br>% of total labor force | 1991–2025 | 234 | 5841/5850 | 99.85% | 229 |
| `SP.POP.TOTL` | Population, total<br>Unit | 1960–2025 | 264 | 6600/6600 | 100.00% | 264 |

### 4.2 IMF WEO current — 8 متغيرات على مستوى الدولة/السنة

| variable_id | التعريف والوحدة | true start–end في workbook | الدول النشطة | observed / expected 2000–2024 | coverage | دول مكتملة 25 سنة |
|---|---|---|---:|---:|---:|---:|
| `NGDP_RPCH` | Gross domestic product (GDP), Constant prices, Percent change<br>Percent | 1980–2031 | 197 | 4847/4925 | 98.42% | 179 |
| `PCPI` | All Items, Consumer price index (CPI), Period average<br>Index | 1980–2031 | 197 | 4829/4925 | 98.05% | 182 |
| `BCA_NGDPD` | Current account balance (credit less debit), Percent of GDP<br>Percent | 1980–2031 | 196 | 4703/4900 | 95.98% | 176 |
| `GGXWDG_NGDP` | Gross debt, General government, Percent of GDP<br>Percent | 1980–2031 | 193 | 4680/4825 | 96.99% | 161 |
| `TM_RPCH` | Imports of goods and services, Volume, Cost insurance freight (CIF), Percent change<br>Percent | 1980–2031 | 176 | 4296/4400 | 97.64% | 162 |
| `TX_RPCH` | Exports of goods and services, Volume, Free on board (FOB), Percent change<br>Percent | 1980–2031 | 177 | 4320/4425 | 97.63% | 162 |
| `LUR` | Unemployment rate<br> | 1980–2031 | 118 | 2794/2950 | 94.71% | 98 |
| `PPPEX` | Rate, Domestic currency per international dollar in PPP terms, ICP benchmarks 2017-2021<br> | 1980–2031 | 197 | 4845/4925 | 98.38% | 188 |

### 4.3 IMF Historical Forecasts — متغيرات ذات بُعد vintage

| variable_id | المعنى | البعد الزمني | السجلات/الخلايا | الفجوات | التحول المنهجي المحفوظ |
|---|---|---|---:|---|---|
| `ngdp_rpch` | real GDP growth، percent | Spring/Fall 1990–2026؛ 2 historical + 6 forecasts لكل إصدار | 8,844 entities × 77 columns | field-level missing داخل vintage-country matrix؛ محفوظ كما هو | IMF يذكر revisions وsplicing وstaff estimates؛ لا collapse |
| `pcpi_pch` | CPI inflation، percent | Spring/Fall 1990–2026 | 8,844 × 77 | محفوظة في CSV matrix | نفس التحذير؛ لا يُخلط مع PCPI current |
| `bca_gdp_bp6` | current account balance، percent GDP | Spring/Fall 1990–2026 | 8,844 × 77 | محفوظة في CSV matrix | نفس التحذير؛ لا تُعامل كقياس ثابت |

### 4.4 EIA INTL — مصفوفة series-by-series

ملف EIA يحتوي **104,407 سلسلة** فعلية ببيانات JSON، وليست 104,407 متغيرات جاهزة للخلط. لكل سلسلة في `VARIABLE_LEVEL_COVERAGE_MATRIX.csv` يوجد `variable_id=series_id`، و`definition/name`، و`unit`، و`native_frequency`، و`true_start_date`، و`true_end_date`، وعدد القيم، و`geography`، و`last_updated`. التوزيع الأصلي هو 100,459 annual و2,159 monthly و1,789 quarterly. لا توجد مصفوفة مشتركة بين هذه السلاسل حتى نختار صراحةً geography/series IDs؛ لذلك لم تُستخدم EIA تلقائياً في panel WDI/IMF.

### 4.5 FRED وNOAA وUCDP وGDELT — لماذا لا تُعامل كـannual values

| الطبقة | المتغيرات الفعلية | التغطية | الفجوات/التحولات المحفوظة | قرار البوابة |
|---|---|---|---|---|
| FRED | `CPIAUCSL` monthly؛ `DCOILWTICO` daily business-day | CPI 1947–2026؛ WTI 1986–2026 | calendar/business-day pattern؛ latest revised series، وليست ALFRED vintages | منفصل؛ لا aggregation في هذه المرحلة |
| NOAA stations | station-element IDs مثل `ASN00015590:PRCP`, `...:TMAX`, `...:TMIN`, وحقول إضافية | 9 محطات؛ station spans 1941–2026، وكل العناصر المختارة تغطي inventory window 2000–2025؛ observed rows لكل field في matrix | station reporting gaps، flags، source/quality attributes؛ لا TAVG synthesized ولا filling | daily environmental layer منفصل |
| UCDP GED | 49 event fields، 417,968 records، 1989–2025 | daily/event/geocoded | date precision، source fields، death uncertainty، event clarity؛ لا event-to-year aggregation | event layer منفصل |
| UCDP/PRIO | 28 conflict-year fields، 2,816 records، 1946–2025 | annual conflict-year، لكن ليس panel اقتصادي مكتمل | conflict coding/version history؛ لا إعادة aggregation | candidate annual conflict bridge لاحقاً |
| GDELT reduced | 17 header fields، archive 1979–2013، payload 6.58 GB غير مفكوك | date-coded reduced country-level event archive | record count وfield-level non-null لم تُحسب لأن archive بقي compressed | event/context archive؛ لا annual conversion |

## 5. التقاطع الزمني والجغرافي الحقيقي

### 5.1 WDI × IMF

التقاطع الذي بُني منه panel هو تقاطع معرفات الدول الموجودة فعلياً في المتغيرات المختارة، وليس تقاطعاً مفترضاً لكل ما في الكتالوج. النتيجة 194 معرفاً، و194 × 25 = 4,850 صفاً. panel يحتفظ بالأسماء في `wdi_entity_name` و`imf_entity_name` وبالأعمدة المصدرية `wdi__...` و`imf__...`، ولا يدمج القيم التي تحمل معنى متشابهاً.

الاكتمال يختلف حسب المتغير: أعلى WDI في هذه القائمة هو `SP.POP.TOTL` بنسبة 100%، يليه `SL.UEM.TOTL.ZS` بنسبة 99.85%. في IMF WEO current، أعلى التغطية هي `NGDP_RPCH` بنسبة 98.42% و`PPPEX` بنسبة 98.38%. الأقل بين المرشحين WDI هو `EG.USE.PCAP.KG.OE` بنسبة 85.07%، ثم صادرات/واردات WDI قرابة 91%، و`LUR` في WEO بنسبة 94.71%. هذه فروق حقيقية وليست فجوات يجوز إغلاقها بالـforward-fill.

### 5.2 ما يمكن ربطه الآن دون اختلاق بيانات؟

يمكن ربط متغيرات WDI وIMF في panel الخام عندما يوجد نفس معرف الدولة وسنة من 2000 إلى 2024، مع إبقاء كل مصدر في عمود مستقل وترك القيم المفقودة فارغة. يمكن أيضاً ربط **الاسم/المعرف** بمرجع provenance، لكن لا يجوز إعلان أن المتغيرين متساويان لمجرد تشابه الاسم؛ مثال ذلك WDI inflation مقابل IMF PCPI، أو WDI GDP growth مقابل IMF NGDP_RPCH. هذا تعارض/مقارنة مصدرية لاحقة، لا averaging.

لا يمكن ربط FRED اليومي أو NOAA اليومي أو GED أو GDELT بالـannual panel الآن من دون تحويل زمني معلن؛ وبما أن المطلوب الحالي عدم تحويل، تبقى منفصلة. كذلك لا يمكن إدخال EIA INTL كعمود واحد؛ لا بد من اختيار series_id وgeography وتغطية فعلية لكل سلسلة أولاً.

## 6. تقييم مرشحي Matrix الأولى

التقييم التالي هو **جاهزية بيانات** فقط. لا يعني أن المرشح تم اعتماده أو أن العلاقة بين متغيراته سببية.

| المرشح | المتغيرات | خلايا observed / expected | تغطية خلوية | دول مكتملة بكل المتغيرات 25 سنة | القراءة |
|---|---|---:|---:|---:|---|
| **macro_with_levels**<br>نمو + GDP per capita + CPI + population + PPP مع IMF growth/CPI/PPP/current account | 9 | 42,510 / 43,650 | 97.39% | 142 | أعلى اكتمال حالياً؛ لكنه لا يضيف طاقة/صراع/بيئة. |
| **core_economic_social**<br>اقتصاد/أسعار/بطالة/سكان مع نمو وتضخم وحساب جارٍ ودين من IMF | 8 | 37,292 / 38,800 | 96.11% | 123 | توازن جيد كبداية محافظة، مع إبقاء trade/energy/conflict خارج النسخة الأولى. |
| **core_plus_trade**<br>المرشح السابق + صادرات/واردات WDI وIMF | 10 | 44,165 / 48,500 | 91.06% | 100 | أغنى من حيث الأدوار الاقتصادية والاجتماعية؛ trade يخفض الجاهزية. |

### التوصية غير المعتمدة بعد

أفضل مرشح جاهز للفحص النهائي قبل التجربة هو **`macro_with_levels`** لأنه يحقق 97.39% من خلايا 2000–2024 و142 دولة مكتملة عبر 9 متغيرات، مع حفظ المقارنات WDI/IMF بدلاً من دمجها. إذا كان الهدف هو عدد أدوار أكبر لا أعلى اكتمال، فـ`core_economic_social` بديل مناسب، لكنه ينخفض إلى 96.11% و123 دولة مكتملة. أما `core_plus_trade` فيضيف دور التجارة بوضوح لكنه ينخفض إلى 91.06% و100 دولة مكتملة؛ لذلك لا أوصي بجعله النسخة الأولى قبل تحديد ما إذا كانت فجوات trade مقبولة أو تستحق تضييق universe الدول.

لا تحتوي أي من هذه المرشحات على UCDP أو EIA أو متغير بيئي فعلي. لذلك فهي ليست بعدُ “المصفوفة متعددة المجالات الكاملة” التي يريدها المشروع؛ إنها **macro readiness candidate** قابلة للمراجعة. لإضافة المجالين اللذين يهمان المشروع، نحتاج أولاً إلى تنزيل UCDP Country-Year الرسمي وفهرسة مجموعة صغيرة من EIA annual series، ثم اختيار مصدر بيئي سنوي/شهري ذي نطاق معلن. لا ينبغي سد هذه الفجوة بتجميع GED أو NOAA أو GDELT تلقائياً.

## 7. البيانات الناقصة التي تمنع اعتماد التجربة

| النقص | أثره | هل يمنع تشغيل Matrix macro صغيرة؟ |
|---|---|---|
| UCDP Country-Year v26.1 لم يُنزّل بعد | لا توجد طبقة سنوية منظمة للعنف/الصراع في panel الحالي | يمنع وصف التجربة بأنها متعددة المجالات سياسياً/اقتصادياً؛ لا يمنع فحص macro-only لاحقاً إذا اعتمد المستخدم ذلك صراحةً |
| EIA series IDs محددة لم تُعتمد | EIA bulk موجود، لكن 104,407 series لا تعني تقاطعاً جغرافياً واحداً | يمنع إدخال الطاقة دون اختلاق/اختيار غير مبرر؛ لا يمنع macro-only |
| متغير بيئي سنوي محدد | WDI precipitation منخفض الاكتمال في هذه القائمة، وNOAA الحالي يومي/محطات | يمنع الادعاء بأن النسخة الأولى تغطي البيئة؛ لا يجوز تحويل اليومي هنا |
| ALFRED vintages مختارة | latest FRED لا يمثل ما كان معروفاً زمنياً | يمنع replay leakage-aware؛ لا يمنع مجرد استخدام FRED latest كمرجع وصفي منفصل |
| Comtrade bounded credentials/scope | التجارة الثنائية/السلعية غير ممثلة فعلياً في panel | يمنع طبقة flows الغنية؛ لا يمنع استخدام trade growth من WDI/IMF مع التصريح بأنه proxy تجميعي |

## 8. الملفات الناتجة

| الملف | المحتوى |
|---|---|
| `/home/ubuntu/market_intelligence_workspace/catalog_first/readiness_gate/VARIABLE_LEVEL_COVERAGE_MATRIX.csv` | مصفوفة 104,565 سجل متغير/field، تشمل WDI وIMF وEIA وFRED وNOAA وUCDP وGDELT. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/readiness_gate/ANNUAL_PANEL_RAW_WDI_IMF_2000_2024.csv` | panel خام 4,850 صفاً، 20 عمود قيمة مصدرية، مع missingness كما هي. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/readiness_gate/ANNUAL_PANEL_READINESS_SUMMARY.json` | أرقام التقاطع والاكتمال والضوابط. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/readiness_gate/VARIABLE_COVERAGE_GATE_SUMMARY.json` | ملخص coverage للمرشحين والـdatasets. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/readiness_gate/FIRST_MATRIX_CANDIDATE_READINESS.json` | مقارنة اكتمال 3 مرشحين بلا تحويلات. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/readiness_gate/FIRST_EXPERIMENTAL_MATRIX_CANDIDATES.json` | قائمة أعمدة المرشحين source-specific. |
| `/home/ubuntu/market_intelligence_workspace/catalog_first/FIRST_MATRIX_CANDIDATES.json` | ملف Catalog-First الأصلي الذي تم التحقق من محتواه. |

## 9. المراجع الرسمية

[1]: https://datatopics.worldbank.org/world-development-indicators/ "World Bank — World Development Indicators"
[2]: https://data.imf.org/en/datasets/IMF.RES:WEO "IMF Data — World Economic Outlook"
[3]: https://ucdp.uu.se/downloads/ "UCDP Dataset Download Center"
[4]: https://www.eia.gov/opendata/index.php#bulk-downloads "EIA Open Data and Bulk Downloads"
[5]: https://fred.stlouisfed.org/series/CPIAUCSL "FRED CPIAUCSL"
[6]: https://alfred.stlouisfed.org/help/downloaddata "ALFRED Download Data Help"
[7]: https://www.ncei.noaa.gov/access "NOAA NCEI Data Access"
[8]: https://www.gdeltproject.org/data.html "GDELT Data"
[9]: https://comtradeplus.un.org/ "UN Comtrade Plus"
[10]: https://earthquake.usgs.gov/fdsnws/event/1/ "USGS FDSN Event Web Service"
