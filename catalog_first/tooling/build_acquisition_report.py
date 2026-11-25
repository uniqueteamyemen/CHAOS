from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
INV = ROOT / 'HISTORICAL_DATASET_ACQUISITION_INVENTORY.csv'
OUT = ROOT / 'HISTORICAL_DATASET_ACQUISITION_INVENTORY_AR.md'
with INV.open(encoding='utf-8', newline='') as handle:
    rows = list(csv.DictReader(handle))

downloaded = [r for r in rows if r['downloaded'] == 'yes']
not_downloaded = [r for r in rows if r['downloaded'] != 'yes']

def esc(text: str) -> str:
    return (text or '').replace('|', '\\|').replace('\n', ' ')

def size(value: str) -> str:
    if not value:
        return '—'
    n = int(value)
    if n >= 1024**3:
        return f'{n / 1024**3:.2f} GiB'
    if n >= 1024**2:
        return f'{n / 1024**2:.1f} MiB'
    if n >= 1024:
        return f'{n / 1024:.1f} KiB'
    return f'{n:,} B'

lines: list[str] = []
lines += [
    '# Historical Dataset Acquisition Inventory',
    '',
    '> **حالة التقرير:** Catalog-First Historical Acquisition — نسخة موثقة من الأصول المحلية والكتالوجات التي تم التحقق منها حتى 26 أغسطس 2026. هذا التقرير ليس تجربة تحليلية، ولا يتضمن تشغيل surrogate جديداً أو تعديلاً للمعمارية أو لبوابات السلامة.',
    '',
    '## 1. الخلاصة التنفيذية',
    '',
    f'أُعيد بناء الجرد من الملفات المحلية المتحققة، ويضم **{len(rows)} مدخلاً**: **{len(downloaded)} مدخلاً نُزّل فعلياً** و**{len(not_downloaded)} مداخل متاحة ككتالوج أو مسار تنزيل ولم تُنزّل بعد**. التنزيلات الفعلية تشمل WDI bulk، وIMF WEO الحالي وتاريخ التنبؤات، وUCDP GED وUCDP/PRIO، وEIA INTL، وسلسلتي FRED، وmetadata ومحطات NOAA المختارة، وأرشيف GDELT reduced. أما Comtrade وALFRED وACLED وEM-DAT وNASA FIRMS وملفات NOAA الشهرية/السنوية العالمية وCountry-Year الإضافي من UCDP فما زالت مسارات متاحة أو مرشحة، وليست حالات غياب للبيانات.',
    '',
    'النتيجة الحاسمة هي أن المشكلة لم تكن غياب datasets تاريخية جاهزة، بل أن الحملة الأولى استخدمت مسار probes ضيقاً. توجد الآن مادة حقيقية كافية للانتقال لاحقاً إلى مصفوفة سنوية متعددة المجالات، لكن لا ينبغي بناء المصفوفة أو تشغيلها قبل حسم قائمة المتغيرات وcoverage الفعلي لكل متغير. أفضل نقطة بداية هي **panel سنوي على مستوى الدولة/التجميع للفترة 2000–2024**، مبني من WDI مع IMF WEO وEIA INTL وطبقة صراعات سنوية من UCDP؛ أما GED وGHCN-Daily وGDELT فتظل طبقة أحداث/يومية منفصلة ولا تُدمج عشوائياً مع السنوي.',
    '',
    '| المؤشر | الحالة المتحققة |',
    '|---|---:|',
    f'| إجمالي مداخل الجرد | {len(rows)} |',
    f'| نُزّل فعلياً مع مسار محلي | {len(downloaded)} |',
    f'| catalog/downloadable ولم يُنزّل | {len(not_downloaded)} |',
    '| إعادة تشغيل تجربة 10,000 surrogate في هذه المرحلة | لا |',
    '| تعديل architecture أو scientific safety gates | لا |',
    '| شراء مصدر مدفوع | لا |',
    '| رفع إلى OneDrive | لا؛ لم يوجد موصل OneDrive متحقق |',
    '',
    '## 2. ما الذي تم تنزيله فعلياً؟',
    '',
    'الجدول التالي هو السجل التشغيلي الأساسي. الأحجام الخام هي أحجام الملفات الأصلية المحتفظ بها، والأحجام المرحلية هي أحجام الاستخراج أو النسخ التي يمكن إعادة بنائها؛ لا تُعامل المرحلة كبديل عن الخام. الأرقام مأخوذة من profiles المحلية، لا من تقدير تقريبي.',
    '',
    '| المصدر / dataset | الإصدار والفترة والتواتر | المتغيرات / السجلات | الحجم الخام → المرحلي | حالة وموضع الحفظ | الدور المقترح |',
    '|---|---|---:|---:|---|---|',
]
for r in downloaded:
    role = r['role_for_first_multivariate_experiment']
    loc = f"raw: `{r['raw_path']}`"
    if r['staged_path']:
        loc += f"<br>staged: `{r['staged_path']}`"
    lines.append(f"| **{esc(r['source'])} — {esc(r['dataset_or_series'])}** | {esc(r['version_vintage'])}<br>{esc(r['years'])}<br>{esc(r['frequency'])} | {esc(r['variables_or_series'])} / {esc(r['records_or_rows'])} | {size(r['raw_size_bytes'])} → {size(r['staged_size_bytes'])} | downloaded<br>{loc}<br>provenance: `{esc(r['provenance_manifest']) or 'داخل metadata/notes المحلية'}` | {esc(role)} |")

lines += [
    '',
    '### 2.1 ملاحظات دقيقة على الأصول الكبيرة',
    '',
    '**WDI** ليس أربع سلاسل فقط. ملف CSV الخام يحتوي جداول observation وcountry وseries وfootnote وغيرها؛ profile المحلي سجل 1,498 series metadata rows و396,970 observation-table rows، مع أعمدة سنوية 1960–2025. metadata يحفظ التعريف والوحدة والدورية والمصدر والقيود وLicense Type. توزيع الترخيص الذي تم فحصه محلياً هو 1,495 سلسلة `CC BY-4.0` وثلاث سلاسل `CC BY 3.0 IGO`، ولذلك لا يجوز اختزال كل السلاسل في عبارة ترخيص واحدة [1].',
    '',
    '**IMF WEO** تم الحصول عليه بصيغتين مختلفتين وظيفياً. `WEOApr2026all.xlsx` هو current vintage يضم مؤشرات اقتصادية وسلعاً وتوقعات؛ أما `WEOhistorical.xlsx` فيضم ثلاثة متغيرات فقط عبر Spring/Fall vintages منذ 1990، ويجب الحفاظ على بُعد vintage وعدم دمج القيم. ملاحظات IMF المحلية تحذر من revisions وsplicing وstaff estimates، ومن اختلاف WEO عن مصادر رسمية أخرى؛ وهذا يجعل الملف مهماً لقياس revision/leakage، لا مصدراً ينبغي فرضه كحقيقة وحيدة [2].',
    '',
    '**UCDP GED** هو سجل أحداث يومية جغرافية مع actors وsource fields وdate precision وdeath estimates، بينما **UCDP/PRIO** conflict-year dataset سنوي من 1946–2025. الأول لا يحل محل الثاني: GED مناسب لطبقة الحدث، وPRIO مناسب لجسر سنوي أولي. ينص مركز UCDP الرسمي على أن التنزيلات الحالية مجانية تحت `CC BY 4.0` مع codebooks وversion history [3].',
    '',
    '**GDELT reduced** محفوظ خاماً مضغوطاً بحجم يقارب 1.09 GB مع checksum، ونجح اختبار سلامة ZIP. يحتوي الأرشيف على payload غير مضغوط يقارب 6.58 GB للفترة 1979–2013، لكنه **لم يُفك ولم يُحلل**. هذا قرار تخزين وتحكم في النطاق، لا فشل تنزيل. بيانات GDELT هي observations مشتقة من الأخبار؛ لا ينبغي تقديمها كقياس ممثل للمجتمع أو كحقيقة سببية [4].',
    '',
    '**NOAA** انتقل من catalog-only إلى تنزيل فعلي محدود ومبرر: نُزّلت ملفات station/inventory/country/README، ثم اختيرت تسع محطات موزعة إقليمياً لأن PRCP/TMAX/TMIN لكل منها يغطي 2000–2025 وفق inventory. ملفات المحطات نفسها تحتفظ بالعناصر المرصودة والسمات؛ لم يتم تركيب TAVG ولم يحدث imputation. لم يتم تنزيل all-station TAR أو GSOM/GSOY الكامل [5].',
    '',
    '## 3. ما وُجد ويمكن تنزيله لكنه لم يُنزّل بعد؟',
    '',
    '| dataset / المسار | ما هو متاح | سبب عدم التنزيل الحالي | القيمة المحتملة |',
    '|---|---|---|---|',
]
for r in not_downloaded:
    lines.append(f"| **{esc(r['source'])} — {esc(r['dataset_or_series'])}** | {esc(r['years'])}; {esc(r['frequency'])}; {esc(r['variables_or_series'])} | {esc(r['failure_or_access_blocker']) or 'لم يُعطَ أولوية في هذه الجولة؛ لا يوجد فشل وصول مثبت.'} | {esc(r['role_for_first_multivariate_experiment'])} |")

lines += [
    '',
    '### 3.1 العوائق مصنفة بدقة',
    '',
    '| الحالة | التفسير الصحيح |',
    '|---|---|',
    '| **Comtrade** | قاعدة التجارة موجودة ومهمة، لكن bulk لملايين السجلات يتطلب اشتراكاً premium وفق صفحة الوصول الحالية؛ المسار المجاني bounded API/preview يحتاج registration/key وحدود pagination. لم يُشترَ شيء، ولا يصح وصف ذلك بأنه غياب للبيانات [6]. |',
    '| **FRED/ALFRED** | فشل مسار FRED-MD المباشر السابق كان HTTP 403 لمسار محدد، وليس غياب FRED. تنزيلات FRED series-level نجحت. ALFRED متاح لتنزيل vintage/real-time، لكن يجب أولاً تحديد series وvintage المطلوبين؛ لا يجوز اعتبار latest FRED ملفاً تاريخياً لما كان معروفاً وقتها [7][8]. |',
    '| **NOAA GSOM/GSOY** | الكتالوج والتنزيل الرسميان متاحان. تم تأجيل GSOM/GSOY الكاملين لأن التجربة الأولى لم تحدد بعد station/phenomenon/geography scope؛ تنزيل كل الملفات لمجرد توفرها يخالف سياسة التخزين الذكي. |',
    '| **GDELT full / BigQuery** | المصدر مفتوح، لكن full Events/GKG كبير جداً؛ reduced archive وحده نُزّل. المسار الصحيح لاحقاً هو streaming/partition/query، لا فك كل الأرشيف محلياً بلا خطة [4]. |',
    '| **ACLED وEM-DAT** | الكتالوجان موجودان، لكن الوصول يتطلب حساباً/شروط استخدام أو registration بحسب المنتج. لم تُستخدم credentials غير موجودة، ولم يُشترَ مصدر. هذه access/terms gates وليست نتائج سلبية عن جودة البيانات [9][10]. |',
    '| **NASA FIRMS** | مسار التنزيل/API متاح، لكن لا توجد بعد مواصفة sensor/date/geography أو MAP_KEY مختارة؛ لذلك لم يُسحب أرشيف حرائق عالمي بلا نطاق [11]. |',
    '| **USGS** | catalog/API query متاح للأحداث الزلزالية؛ لم يُنزّل bulk لأن الاستعلام الجغرافي والزمني يجب أن يحدد أولاً. probes السابقة لا تعني أن catalog غير متاح [12]. |',
    '| **OneDrive** | فُحصت الإعدادات وقائمة الموصلات ولم يظهر موصل OneDrive متاحاً. لذلك لم يتم رفع أي ملف ولم تُفترض صلاحية غير متحققة. |',
    '',
    '## 4. الترشيح العملي لأول مصفوفة حقيقية متعددة المجالات',
    '',
    '### الترشيح الأساسي: panel سنوي country-year/aggregate للفترة 2000–2024',
    '',
    'هذه ليست تجربة منفذة بعد، بل **مواصفة اختيار** قبل التجربة. الفترة 2000–2024 تعطي 25 سنة تقويمية مكتملة تقريباً وتتفادى إدخال سنة 2025 التي قد تكون غير مكتملة أو قابلة للمراجعة في بعض المصادر. يجب أولاً اختيار الدول/التجمعات التي تظهر فعلياً في المتغيرات المختارة؛ لا يُنشأ قاموس كيانات شامل لمجرد وجود دول في metadata.',
    '',
    '| طبقة | dataset المرشح | ما الذي يدخل مبدئياً | ضابط الاستخدام |',
    '|---|---|---|---|',
    '| اقتصاد وتنمية | WDI bulk CSV | عدد صغير من السلاسل ذات تعريف ووحدة وتغطية واضحة: ناتج/نشاط، أسعار أو قوة شرائية، تجارة، طاقة/بيئة، وسكان أو بنية اجتماعية عند الحاجة | اختيار variable-level لا topic-level؛ الاحتفاظ بالقيم الخام والمصدر والقيود وعدم ملء الفجوات |',
    '| اقتصاد كلي ومراجعات | IMF WEO April 2026 + WEO Historical Forecasts | مؤشرات النمو والتضخم والحساب الجاري/المالية أو السلع، مع current-vintage منفصل عن vintage replay | لا averaging مع WDI؛ WEO historical يستخدم للـvintage/leakage/revision، لا كقيمة بديلة تلقائية |',
    '| طاقة | EIA INTL | سلاسل سنوية مختارة ذات تغطية 2000–2024 وتعريف صريح، مثل استهلاك الطاقة/الناتج أو إنتاج/استهلاك طاقة حسب النطاق | لا تستخدم envelope 104,407 series كأنها مصفوفة مكتملة؛ profile لكل series ثم coverage matrix |',
    '| صراع/عنف منظم | UCDP Country-Year v26.1، مع UCDP/PRIO المتاح كمرجع | متغيرات country-year منظمة العنف، أو conflict-year presence/intensity حيث يناسب التعريف | يفضّل تنزيل Country-Year الرسمي قبل بناء aggregation يدوي من GED؛ GED يبقى منفصلاً |',
    '| سوق/سلعة عالمية | FRED DCOILWTICO، وربما CPIAUCSL كمرجع شهري | سياق سلعي/سعري عالمي، لا كبديل عن EIA أو WDI | يحافظ على daily/monthly native frequency؛ السنوي derived فقط في alignment layer معلنة |',
    '| متغير بيئي | لا يُفرض في المصفوفة السنوية قبل الاختيار | إمّا GSOM/GSOY محدد النطاق أو WDI climate/environment series ذات coverage مناسب | لا تنزيل GSOY/GSOM العالمي ولا z-score عالمي قبل تحديد الظاهرة وbaseline |',
    '',
    '### قائمة WDI المرشحة للفحص قبل بناء المصفوفة',
    '',
    'هذه الأكواد ليست DAGاً مفروضاً ولا متغيرات نهائية؛ إنها shortlist metadata يجب فحص coverage الفعلي لها على مستوى الدولة/السنة قبل أي اختبار: `NY.GDP.MKTP.KD` (GDP constant 2015 US$)، `NY.GDP.MKTP.KD.ZG` (GDP growth)، `NY.GDP.PCAP.KD` (GDP per capita)، `FP.CPI.TOTL.ZG` (CPI inflation)، `PA.NUS.PPP` (PPP conversion factor)، `NE.EXP.GNFS.KD.ZG` و`NE.IMP.GNFS.KD.ZG` (exports/imports growth)، `EG.USE.PCAP.KG.OE` (energy use per capita)، `AG.LND.PRCP.MM` (average precipitation)، `EN.ATM.CO2E.PC` إذا كانت تغطيته مناسبة، `SP.POP.TOTL` (population)، و`SL.UEM.TOTL.ZS` (unemployment). القائمة الآلية الكاملة وحقول الوحدة والمصدر والترخيص محفوظة في `FIRST_MATRIX_CANDIDATES.json`؛ لم تُستخدم لإنتاج نتائج سببية.',
    '',
    'النتيجة العملية: **أولوية الاقتناء التالية ليست GDELT الكامل ولا all-station NOAA ولا Comtrade premium، بل UCDP Country-Year v26.1، ثم اختيار وفهرسة مجموعة صغيرة من EIA annual series، ثم تحديد طبقة بيئية سنوية أو شهرية ذات نطاق واضح.** بعد ذلك فقط تُبنى coverage matrix على مستوى المتغير، ويُقرر إن كانت المصفوفة السنوية غنية بما يكفي للتجربة.',
    '',
    '### المسار البديل المنفصل: تجربة أحداث يومية/بيئية',
    '',
    'يمكن لاحقاً تصميم طبقة مستقلة من UCDP GED + محطات GHCN-Daily المختارة + USGS أو FIRMS + جزء محدد من GDELT. هذه التجربة لا ينبغي أن تُدمج مباشرة مع panel السنوي؛ لأن event timestamps، ودقة التاريخ، وmissingness، ومعنى الخبر أو الحدث تختلف جذرياً عن القياسات السنوية. أي تحويل إلى شهر/سنة يجب أن يكون اشتقاقاً معلناً يحفظ الأصل، وليس استبدالاً للبيانات الأصلية.',
    '',
    '## 5. قواعد الحوكمة التي بقيت نافذة',
    '',
    'يبقى الخام immutable مع checksum ووقت الوصول ونسخة المصدر. تبقى الطبقات المرحلية قابلة للحذف وإعادة البناء ولا تُعامل كمصدر أصلي. لا يوجد forward-fill أو back-fill أو interpolation شامل، ولا متوسط قسري بين WDI وIMF وEIA وFRED. تُحفظ التناقضات كـsource contrasts، ويُسجل لكل اشتقاق source references والتحويل والتواتر والتسرب الزمني المحتمل.',
    '',
    'الزمن هنا قيد ترتيب ومكوّن في اختبار precedence أو information flow، وليس برهاناً على السببية. أي candidate structural pattern يجب أن يمر لاحقاً عبر تصحيح تعدد الاختبارات، اختبار خارج العينة زمني، اختبار استقرار، وسجل rejected مستقل. لم تتغير هذه البوابات ولم يُعاد تشغيل baseline الحالي ذي 36 edge-lag و0 validated و36 rejected.',
    '',
    '## 6. الملفات الناتجة ومواقعها',
    '',
    '| الملف | الغرض |',
    '|---|---|',
    f'| `{INV}` | CSV الآلي الكامل، 22 مدخلاً، مناسب للقراءة البرمجية والفرز حسب المصدر أو حالة التنزيل. |',
    f'| `{OUT}` | هذا التقرير العربي التفصيلي. |',
    f'| `{ROOT / "workbook_profile.json"}` | profile WDI وIMF الحالي والتاريخي. |',
    f'| `{ROOT / "ucdp_profile.json"}` | profile GED وPRIO. |',
    f'| `{ROOT / "eia_intl_profile.json"}` | profile EIA INTL. |',
    f'| `{ROOT / "fred_eia_profile.json"}` | profile FRED/EIA raw assets. |',
    f'| `{ROOT / "noaa_station_profile.json"}` | profile المحطات التسع المنزلة. |',
    f'| `{ROOT / "FIRST_MATRIX_CANDIDATES.json"}` | shortlist آلي للمرشحين من WDI وEIA؛ catalog metadata فقط. |',
    f'| `{ROOT / "official_source_notes_2026-08-26.md"}` | سجل الصفحات الرسمية التي تم فحصها وروابطها. |',
    '',
    '## المراجع الرسمية',
    '',
    '[1]: https://datatopics.worldbank.org/world-development-indicators/ "World Bank — World Development Indicators"',
    '[2]: https://data.imf.org/en/datasets/IMF.RES:WEO "IMF Data — World Economic Outlook"',
    '[3]: https://ucdp.uu.se/downloads/ "UCDP Dataset Download Center"',
    '[4]: https://www.gdeltproject.org/data.html "GDELT — Data"',
    '[5]: https://www.ncei.noaa.gov/access "NOAA NCEI — Data Access"',
    '[6]: https://comtradeplus.un.org/ "UN Comtrade Plus"',
    '[7]: https://fred.stlouisfed.org/series/CPIAUCSL "FRED — CPIAUCSL"',
    '[8]: https://alfred.stlouisfed.org/help/downloaddata "ALFRED — Download Data Help"',
    '[9]: https://acleddata.com/ "ACLED — Armed Conflict Location & Event Data"',
    '[10]: https://www.emdat.be/ "EM-DAT — The International Disaster Database"',
    '[11]: https://firms.modaps.eosdis.nasa.gov/ "NASA FIRMS"',
    '[12]: https://earthquake.usgs.gov/fdsnws/event/1/ "USGS FDSN Earthquake Event Web Service"',
]
OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'wrote {OUT} with {len(rows)} inventory rows; downloaded={len(downloaded)}; not_downloaded={len(not_downloaded)}')
