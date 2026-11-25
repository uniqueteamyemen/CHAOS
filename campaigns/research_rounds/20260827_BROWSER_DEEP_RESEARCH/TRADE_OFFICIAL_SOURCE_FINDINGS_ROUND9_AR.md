# CHAOS — IMF Data: نتيجة مسار Search Results

بعد محاولة تحديد بطاقة `International Trade in Goods (by partner country) (IMTS)` داخل كتالوج IMF، انتقلت الواجهة إلى Search Results عامة تحتوي على 22,457 نتيجة موزعة بين datasets وindicators وtables وdashboards. ظهرت WEO وغيرها في نتائج عامة، ولم تُفتح بطاقة IMTS مباشرة من هذه الشاشة.

تُحفظ نتيجة الجولة السابقة التي أثبتت ظهور ITG وIMTS في صفحة datasets المصفاة. أما هذه الخطوة فتثبت أن بحث IMF العام لا يكفي لاستخراج dataset ID، وأن فتح البطاقة/metadata يجب أن يتم من صفحة datasets المصفاة أو عبر رابط رسمي مستخرج من HTML/الواجهة.

لا توجد عملية تنزيل أو Edge جديدة من IMF في هذه الخطوة. الحالة: `IMF_ITG_IMTS_catalog_confirmed_download_pending`.

## HTML inspection

تحليل HTML المحفوظ من Search Results لم يُظهر روابط نصية أو href مباشرة لـITG/IMTS. لذلك لا يُنشأ endpoint بالحدس، ولا يُسجل IMF كملف منزّل في هذه الجولة. الحاجة المتبقية هي رابط بطاقة dataset من الواجهة أو API/SDMX رسمي موثق.

## واجهة IMF: قيد تفاعلي إضافي

أُعيد فتح صفحة IMF المصفاة التي تعرض ITG وIMTS، لكن محاولة تمرير الصفحة إلى عناصر البطاقة أعادت HTTP 504 من امتداد المتصفح. بقيت أوصاف dataset الظاهرة في الصفحة محفوظة، ولم يتم تنزيل ITG/IMTS أو اختلاق رابط. تُصنف الحالة كـ`dataset_discovered_ui_scroll_timeout`.
