# CHAOS — WTO Stats: حالة التفاعل مع اختيار المؤشرات

المصدر الرسمي: https://stats.wto.org/inventory/en

تم فتح Database Inventory من واجهة WTO Stats، ثم فتح قسم Merchandise trade statistics. ظهرت حالة اختيار أولية `28 / 55` مؤشراً، مع وجود خيارات CSV وExcel وLink وAPI في منطقة العرض، وأبعاد Reporting Economies وProducts/Sectors وPartner Economies وYears.

تم إدخال مرشح بحث `merchandise trade` في حقل المؤشرات، لكن الواجهة لم تعرض بعد ملفاً أو نتيجة قابلة للتنزيل في النص المستخرج. لذلك لا يُسجل أي WTO dataset جديد أو download في هذه المرحلة. الحالة الحالية هي `interactive_selection_available_export_not_completed`.

لا توجد نتيجة رقمية أو Edge مستخرجة من WTO في هذه الجولة، ولا يجوز استخدام الاختيار الافتراضي أو عدد المؤشرات كأنه panel تاريخية.

## فشل تفاعل موثق

محاولة تطبيق المرشح عبر زر Enter أعادت HTTP 504 من امتداد المتصفح. لم يتم تنزيل أو تعديل أي بيانات، وسُجلت الحالة كـ`browser_interaction_timeout` لا كفشل في WTO نفسه.
