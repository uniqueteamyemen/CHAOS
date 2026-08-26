# جرد فجوة الكتالوجات والـDatasets الجاهزة

## نطاق الجرد

هذا الجرد مبني على الملفات الموجودة فعلياً في مساحة العمل وسجل البحث وسجل المصادر التشغيلي. لم تُجرَ أي طلبات شبكة جديدة أثناء إعداد الجرد، ولم تُعتبر أسماء datasets أو روابط الوثائق دليلاً على تنزيل dataset فعلي.

## الخلاصة التنفيذية

الحملة الحالية لم تنفذ استراتيجية catalog-first أو bulk/archive-first. لقد عرّفت World Bank على أنه `metadata_and_selected_indicators`، وعرّفت IMF على أنه `catalog_metadata_first`، وعرّفت معظم المصادر الأخرى على أنها probes أو bounded extracts. ثم جرى تنفيذ خمس سلاسل World Bank وعينة Comtrade صغيرة وملف IMF وملف USGS. لذلك فالفجوة الأساسية كانت **فجوة مسار جمع واختيار** قبل أن تكون فجوة تقنية.

كان هناك أيضاً عوائق وصول حقيقية: FRED أعاد 403 لمسارات FRED-MD المختبرة، NOAA واجه فشل TLS/اتصال، GDELT أعاد 404 للمسار الأرشيفي المتوقع، وACLED/UCDP/EM-DAT تتطلب حساباً أو token أو وصولاً مقيداً. لكن هذه العوائق لا تفسر عدم تنزيل World Bank catalog أو IMF bulk/SDMX أو Comtrade bulk؛ تلك المسارات لم تُنفذ كحملة catalog-first كاملة.

## ما يوجد فعلياً الآن

| المصدر | dataset أو payload الموجود فعلياً | السنوات/التواتر | الحجم والسجلات | حالة الملف | التفسير |
|---|---|---|---:|---|---|
| World Bank WDI | `NY.GDP.MKTP.KD` العالمي | 2000–2025، سنوي | 26 قيمة، 5,574–5,941 bytes حسب النسخة | جاهز كسلسلة منفردة | ليس كتالوجاً ولا bulk dataset |
| World Bank WDI | `FP.CPI.TOTL.ZG` العالمي | 2000–2025، سنوي | 26 قيمة، 5,941 bytes | جاهز كسلسلة منفردة | لا يمثل كل سلاسل WDI |
| World Bank WDI | `EG.USE.PCAP.KG.OE` العالمي | 2000–2025، سنوي | 26 قيمة، 6,171 bytes | جاهز كسلسلة منفردة | لا يمثل الطبقة البيئية/الطاقة كاملة |
| World Bank WDI | `SP.POP.TOTL` العالمي | 2000–2025، سنوي | 26 قيمة، 5,188 bytes | جاهز كسلسلة منفردة | سلسلة منفردة |
| World Bank WDI | `NE.TRD.GNFS.KD.ZG` العالمي | 2000–2025، سنوي | 0 قيمة، 102 bytes | حمولة بلا ملاحظات | يجب ألا تُعامل كبيانات ناقصة قابلة للتخمين |
| IMF DataMapper | payload خام يحتوي مؤشرات IMF | 1980–2031 في الحمولة، سنوي | 10,914 قيمة تقريباً و229 مؤشراً بحسب الفهرس المحلي، 121,723 bytes | **أكبر payload جاهز فعلياً حالياً** | يحتوي تاريخاً وتوقعات؛ يجب فصل التاريخي عن التوقعات قبل التحليل |
| USGS NWIS | سلسلة Daily Values لموقع/معلمة محددة | 2000–2025، يومي | 9,497 قيمة تقريباً، 700,591 bytes | dataset محدود جاهز | ليس أرشيف USGS كاملاً ولا شبكة مواقع |
| UN Comtrade | واردات أستراليا 2022، `TOTAL`، كل الشركاء، HS | 2022، سنوي | سجل تجارة واحد، 972 bytes | preview حقيقي | ليس bulk ولا تاريخاً متعدد السنوات |
| EIA | استجابة جذر/metadata | غير منطبق | 3,114 bytes | probe metadata | لا توجد سلسلة طاقة جاهزة في المخزن |
| FRED | استجابات 403 لمسارات FRED-MD | غير منطبق | 243–263 bytes لكل probe | access exception | ليست datasets؛ هي XML AccessDenied محفوظ كما وصل |
| GDELT | `lastupdate`/استجابة metadata ومحاولات أرشيف 404 | غير منطبق | 320 bytes وملفات استثناء | probe/exception | لا يوجد event archive محفوظ |
| NOAA | سجل فشل TLS/اتصال لمسار أرشيف | غير منطبق | لا توجد حمولة | exception | لا توجد dataset NOAA جاهزة |
| ACLED | لا يوجد payload | غير منطبق | لا يوجد ملف بيانات | credentials required | لم يُستخدم |
| UCDP | لا يوجد payload | غير منطبق | لا يوجد ملف بيانات | token required | لم يُستخدم |
| EM-DAT | لا يوجد payload | غير منطبق | لا يوجد ملف بيانات | account/portal access | لم يُستخدم |
| NASA FIRMS | وثائق/بحث فقط | لا يوجد تنزيل | لا يوجد ملف بيانات | not captured | archive يحتاج Earthdata/access route |
| World Bank CCKP | وثائق/بحث فقط | لا يوجد تنزيل | لا يوجد ملف بيانات | not captured | لم تُنفذ حملة تنزيل |

## أين حُفظ ما نُزّل فعلياً؟

| المجموعة | المسار |
|---|---|
| كل الاستجابات الخام | `/home/ubuntu/market_intelligence_workspace/campaign/raw/` |
| World Bank الخمس | الجولة `20260825T201223Z/` داخل `campaign/raw/` |
| World Bank GDP الأولي | الجولة `20260825T200702Z/` داخل `campaign/raw/` |
| IMF وUSGS وEIA وFRED وGDELT probes | الجولة `20260825T200543Z/` داخل `campaign/raw/` |
| FRED-MD 403 responses | الجولة `20260825T200726Z/` داخل `campaign/raw/` |
| UN Comtrade preview | الجولة `20260825T200757Z/` داخل `campaign/raw/` |
| NOAA exception | الجولة `20260825T200819Z/` داخل `campaign/raw/` |
| GDELT archive exceptions | الجولة `20260825T201050Z/` داخل `campaign/raw/` |
| مصفوفة World Bank المشتقة | `/home/ubuntu/market_intelligence_workspace/structural_engine/derived/annual_observed_matrix.csv` |

## datasets الجاهزة التي وُجدت في البحث ولم تُنزّل

المقصود هنا datasets حقيقية أو archives جاهزة في المصدر، لا مجرد endpoints:

| المصدر | dataset/archive الذي كان ينبغي فحصه | حالة الاستخدام في الحملة | السبب المثبت لعدم الاستخدام |
|---|---|---|---|
| World Bank | كتالوج WDI والمؤشرات القابلة للاكتشاف عبر Indicators API | لم يُنزّل كتالوجاً | لم تُنفذ مرحلة catalog enumeration؛ اختيرت خمس سلاسل يدوياً |
| FRED/ALFRED | FRED series/observations وFRED-MD وvintage dates | لم تُنزّل بيانات | 403 للمسارات المختبرة؛ API key ومسار وصول رسمي مناسب لم يُستكمل |
| IMF | WEO/SDMX datasets وvintages | جُمع DataMapper payload واحد، لا bulk WEO كامل | لم تُنفذ حملة SDMX catalog/bulk كاملة؛ portal/API structure يحتاج تثبيت dataset keys |
| UN Comtrade | bulk/API datasets حسب reporter/partner/flow/commodity/period | preview لسجل واحد فقط | لم يُنفذ تعريف bulk query ولا pagination/archive campaign |
| NOAA | NCEI datasets/archives وAccess Data Service | لم تُنزّل dataset | فشل اتصال/TLS للمسار المحدد؛ لم يُنفذ مسار بديل ناجح |
| GDELT | Event Database/GKG archives أو BigQuery partitions | لم تُنزّل dataset | مسار archive naming المتوقع أعاد 404؛ لم يُكتشف catalog الحالي أو BigQuery partition route |
| EIA | API v2 catalog/facets/series | metadata root فقط | مفتاح مجاني مطلوب ولم تُنفذ سلسلة محددة بمفتاح |
| ACLED | API/Explorer event dataset | لم يُنزّل | حساب/token مقيد |
| UCDP | GED وCountry-Year وArmed Conflict datasets | لم يُنزّل | token مطلوب |
| EM-DAT | public portal disaster dataset | لم يُنزّل | حساب/شروط وصول |
| NASA FIRMS | science-quality MODIS/VIIRS archive | لم يُنزّل | Earthdata/archive access لم يُنفذ |
| CCKP | historical climate/hazard datasets | لم يُنزّل | لم تُنفذ حملة وصول/تنزيل |

## ما هو العائق الحقيقي؟

| السبب | أمثلة | الحكم |
|---|---|---|
| اختيار مسار جمع ضيق | World Bank خُصصت له خمس سلاسل بدلاً من catalog enumeration؛ Comtrade اختُزل إلى preview؛ IMF لم يتحول إلى bulk campaign | **السبب الرئيسي** |
| credentials أو account | FRED API، EIA key، ACLED، UCDP، EM-DAT، NASA FIRMS archive | عائق حقيقي لبعض المصادر |
| مسار وصول خاطئ أو غير مكتشف | GDELT archive 404، FRED-MD 403، NOAA TLS | عائق تقني قابل للمعالجة، لا دليل على غياب dataset |
| حجم البيانات | GDELT GKG والأرشيفات الكبيرة | يتطلب extraction محدداً أو partitions، لا probe صغيراً |
| الترخيص | لم تُحفظ تراخيص كل dataset في provenance الحالي | فجوة توثيق؛ لا يجوز افتراض الإتاحة لإعادة التوزيع |
| عدم وجود dataset | لم يثبت أن المصادر لا تملك البيانات | لم يكن هناك فحص catalog/archive كافٍ |

## أكبر datasets الجاهزة القابلة للاستخدام من الموجود حالياً

بحسب الملفات المحلية، وليس حسب إمكانية الوصول المستقبلية، الترتيب هو:

1. **IMF DataMapper payload**: أكبر payload خام موجود، لكنه ليس WEO bulk archive كاملاً، ويحتاج فصل التاريخي عن التوقعات وتثبيت تعريف المؤشرات.
2. **USGS NWIS Daily Values**: 9,497 ملاحظة يومية تقريباً لسلسلة محددة؛ مناسب لتجربة daily native-frequency، وليس شبكة مياه واسعة.
3. **World Bank WDI individual series**: أربع سلاسل مكتملة للفترة 2000–2025، مناسبة لبناء matrix سنوية صغيرة، وليست dataset واسعة.
4. **UN Comtrade preview**: سجل تجارة واحد فقط؛ صالح لاختبار schema/provenance، وغير صالح كتحليل تاريخي.

## ما الذي كان ينبغي أن يحدث؟

كان ينبغي أن تبدأ الحملة بطبقة **Catalog Discovery** لكل مصدر، ثم تنشئ `Dataset Inventory` يسجل كل dataset/series المتاح وتعريفه وتواتره وتغطيته وحجمه وترخيصه وطريقة الوصول. بعد ذلك نختار مجموعة متغيرات مرتبطة بالظواهر، وننفذ bulk أو archive extraction على datasets جاهزة، مع حفظ الخام والإصدارات.

في حالة World Bank تحديداً، كان ينبغي تنزيل أو فهرسة catalog metadata أولاً، ثم اختيار سلاسل على مستوى الظاهرة/المتغير، مثل الإنتاج والأسعار والعمل والتجارة والطاقة والبيئة والصحة والديموغرافيا، بدلاً من القفز مباشرة إلى خمس سلاسل عالمية. الرقم 16,000 أو 19,000 يصف حجم الكتالوج بحسب طريقة العد والإصدار، وليس عدد أحداث جاهزة في ملف واحد؛ لذلك يجب تثبيت العدد من استجابة الكتالوج نفسها قبل استعماله كرقم نهائي.

## الحكم النهائي

الحملة الحالية كانت **اختبار اتصال وإثباتاً لسلامة حفظ الخام**، وليست حملة استخراج datasets تاريخية جاهزة. لقد استخدمت بعض البيانات الحقيقية، لكنها لم تستثمر catalogues الواسعة كما طلبت المسودة. لذلك الإجابة الصريحة هي:

> **المشكلة كانت أساساً في اختيار مسار الجمع وتنفيذه، مع عوائق وصول حقيقية لبعض المصادر. لم يكن السبب أن datasets الجاهزة غير موجودة.**

ولا ينبغي اتخاذ قرار شراء أو استبعاد مصدر قبل تنفيذ جرد catalog/archive فعلي لكل مصدر، مع الفصل بين «كتالوج موجود»، و«dataset قابل للتنزيل»، و«dataset نُزّل فعلاً»، و«dataset صالح للتحليل بعد تثبيت تعريفه وترخيصه».

## الأدلة المحلية

- سجل المصادر: `/home/ubuntu/market_intelligence_workspace/source_registry.json`
- جرد الملفات: `/home/ubuntu/market_intelligence_workspace/existing_dataset_inventory.csv`
- سجل البحث: `/home/ubuntu/market_intelligence_research_notes.md`
- فهرس الخام: `/home/ubuntu/market_intelligence_workspace/campaign/RAW_STORE_MANIFEST.txt`
- تقرير الجودة: `/home/ubuntu/market_intelligence_workspace/campaign/QUALITY_EXCEPTION_REPORT.md`
