# IMF IMTS — نتيجة بطاقة المصدر الرسمية

في 27 أغسطس 2026 فُتحت بطاقة IMF الرسمية مباشرة:

`https://data.imf.org/en/datasets/IMF.STA:IMTS`

العنوان الرسمي: `International Trade in Goods (by partner country) (IMTS)`، مع وصف أن البيانات تشمل إحصاءات صادرات وواردات السلع موزعة حسب الشركاء التجاريين، وأنها كانت تُعرف سابقاً باسم DOTS. التواتر الظاهر: Annual, Monthly, Quarterly. الناشر: IMF Statistics Department (STA).

تظهر في البطاقة عناصر `API` و`VIEW DATA` و`DOWNLOAD`. عند فتح `DOWNLOAD` ظهرت نافذة `Download Dataset` وبداخلها زر تنزيل رسمي، لكن النافذة كانت ما تزال في حالة تحميل/عرض فارغ عند حفظ هذه الملاحظة. لم يتم الضغط على Download بعد، ولم يتم تنزيل ملف أو معرفة صيغة/حجم التنزيل في هذه الخطوة.

الحالة: `official_dataset_card_confirmed_download_dialog_open_pending_selection_or_load`.

قاعدة الجولة: لا يُبنى adapter ولا تُنشأ observations قبل تثبيت صيغة الملف، vintage، الوحدات، الأبعاد، ونطاق السنوات من نافذة التنزيل أو API الرسمي.

## إطلاق التنزيل

بعد تثبيت العقد، تم الضغط على زر `DOWNLOAD` الرسمي. ظهرت رسالة الواجهة: `The file will start downloading shortly.` وبقيت نافذة IMTS مضبوطة على `Download full dataset` و`File Format: CSV` و`Data format: Timeseries per row`. لم يُثبت اكتمال الملف أو حجمه بعد؛ الخطوة التالية هي فحص `chrome://downloads` وملف Downloads محلياً ثم نقله إلى مسار raw immutable مع SHA.

## فحص التنزيل

محاولة فتح `chrome://downloads/` في My Browser أعادت: `Could not establish connection. Receiving end does not exist.` لذلك لم أعتبر رسالة إطلاق التنزيل دليلاً على اكتمال الملف. سيُفحص `/home/ubuntu/Downloads/` محلياً، وتبقى الحالة pending حتى يظهر ملف مكتمل يمكن حساب SHA له.

## Structure API الرسمي

استُخدم المسار الذي تكشفه واجهة IMF نفسها:

`https://api.imf.org/external/sdmx/3.0/structure/dataflow/IMF.STA/IMTS/1.0.0?detail=full&references=all`

أعاد HTTP 200 بصيغة `application/vnd.sdmx.structure+json;version=2.0` وبحجم 2,665,607 بايت. أكد response أن dataflow هو `IMF.STA:IMTS(1.0.0)`، وأن ترتيب dimensions هو: `COUNTRY`، `INDICATOR`، `COUNTERPART_COUNTRY`، `FREQUENCY`. كما أكد codelists الأساسية: `CL_IMTS_COUNTRY` بعدد 359 كوداً، `CL_IMTS_INDICATOR` بعدد 4، `CL_FREQ` بعدد 34، و`CL_TRADE_FLOW` بعدد 50. هذا يثبت أن بنية reporter/counterpart/frequency حقيقية في المصدر، ولا يزال طلب observations نفسه قيد التنفيذ.

## أول query observations ناجح

الـquery الرسمي الذي استخدم `c[TIME_PERIOD]=ge:2000-01-01+le:2024-12-31` أعاد HTTP 200 بصيغة CSV وحجماً 1,479,297 بايت. على `USA.XG_FOB_USD.*.A` أعاد 2,437 observation رقمية كاملة: الولايات المتحدة، مؤشر الصادرات FOB بالدولار، Annual، السنوات 2000–2024، و100 counterpart country. الوحدات `USD`، scale=`6`، trade flow=`XG`. الـlimit=100 حدّد عدد سلاسل الشركاء تقريباً، لذلك سيُختبر extract متعدد البلدان مع limit أعلى قبل بناء adapter.

SHA-256 للاستجابة: `5eb48534a3f1893e2cf55f74258e0c4819f7ea0d630dd0d078a748832ff18763`.

## التوسعة متعددة البلدان ونتيجة Edge

اكتُسبت استجابات منفصلة لـ15 reporter (`USA, CHN, DEU, JPN, IND, GBR, FRA, ITA, CAN, KOR, BRA, MEX, SAU, TUR, ZAF`) لمؤشري `XG_FOB_USD` و`MG_FOB_USD`، وكل counterpart، Annual، 2000–2024، بحد `limit=5000` لكل reporter. أعادت الاستجابات HTTP 200، وبلغت مخرجات adapter 102,495 observation و239 counterpart code. جميع reporters الخمسة عشر مكتملون في XG عبر 25 سنة، بينما MG مكتمل لأربعة reporters فقط.

أُجريت Edge جديدة بعقد مستقل: `IMF IMTS XG_FOB_USD reporter-to-G001 raw contraction → WDI material GDP deterioration`. عبر 15 reporter و315 origin rows، كان confirmation max risk difference سالباً `-0.2226720648`، وnull داخل reporter أعطى `p=0.99940006`. لذلك سُجلت Edge بالحالة `rejected`؛ لا positive composition ولا causal claim. هذه النتيجة تغلق هذا التعريف التجريبي ولا تستدعي إعادة ملاءمة العتبات داخله.
