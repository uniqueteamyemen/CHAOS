# CHAOS — OECD PMR: تنزيل رسمي عبر المتصفح

المصدر الرسمي: https://data-explorer.oecd.org/vis?tenant=archive&df[ds]=DisseminateArchiveDMZ&df[id]=DF_PMR&df[ag]=OECD

تم فتح خيار Download ثم اختيار `Unfiltered data in tabular text (CSV)` من واجهة OECD Data Explorer Archive. أكدت الصفحة أن التنزيل أُطلق. الملف الناتج سيُفحص في `/home/ubuntu/Downloads/` للتحقق من الاسم والحجم والهاش والحقول، ثم يُحفظ كـraw خارج Git أو ضمن مسار raw المتجاهل، مع إنشاء manifest مشتق فقط.

النسخة التي نزلت هي `Product Market Regulation 2013.`، بعدد نقاط بيانات غير مفلترة `4,134` وآخر تحديث ظاهر `29 February 2024`. لا يجوز مساواتها تلقائياً بتحديث PMR 2023–2024 في صفحة موضوع OECD؛ الإصداران سيبقيان منفصلين.

الحالة: `download_launched_pending_local_file_verification`.

## Fallback موثق للرابط الرسمي

بعد استخراج رابط SDMX الرسمي من HTML، تعذر فتحه من My Browser بسبب `Receiving end does not exist`. هذا انقطاع في اتصال المتصفح لا في مصدر OECD. سيُستخدم الرابط المستخرج نفسه عبر fallback شبكي قابل للحفظ مع hash وHTTP metadata، ثم تُعامل النتيجة كـraw OECD منفصل، لا كاستبدال لنتائج الحملة السابقة.

الرابط الرسمي غير المفلتر: `https://sdmx.oecd.org/archive/rest/data/OECD,DF_PMR,/all?dimensionAtObservation=AllDimensions&format=csvfilewithlabels`

## Reference information: فشل موثق

الرابط الرسمي المستخرج من صفحة OECD لـ`Unfiltered reference information` أعاد HTTP `422 Unprocessable Entity` عند fallback الشبكي. لم تُسجل استجابة reference information كملف صالح، ولم يُستخدم أي محتوى منها. تبقى observations PMR الخام والـmetadata الظاهرة في Data Explorer هي الأدلة المقبولة حالياً، ويُسجل endpoint كـ`official_reference_endpoint_422` إلى أن يُكتشف مسار API أحدث موثق.
