# CHAOS — OECD PMR: نتيجة الوصول إلى dataset عبر Data Explorer Archive

المصدر الرسمي: https://data-explorer.oecd.org/vis?tenant=archive&df[ds]=DisseminateArchiveDMZ&df[id]=DF_PMR&df[ag]=OECD

أعاد الرابط التاريخي `DataSetCode=PMR` التوجيه إلى OECD Data Explorer Archive، حيث ظهر dataset باسم `Product Market Regulation 2013.`. أظهرت الصفحة أن عدد نقاط البيانات غير المفلترة هو `4,134`، وأن آخر تحديث معروض هو `29 February 2024`. الواجهة تعرض اختيار Year وIndicator وCountry، إضافة إلى Table وChart وDownload وDeveloper API.

هذا يثبت أن PMR dataset قابل للوصول عبر archive، لكنه يثبت أيضاً أنه إصدار 2013/Archive وليس بالضرورة أحدث موجة 2023–2024 التي وصفتها صفحة الموضوع. لذلك يجب فصل الإصدارين وعدم دمجهما أو اعتبارهما سلسلة سنوية واحدة. يلزم تنزيل/تصدير PMR Archive أو الوصول إلى dataset الحالي مع metadata قبل بناء DomainStates أو Edge.

الحالة: `official_dataset_access_confirmed_archive_vintage_2013; current_wave_unconfirmed`.
