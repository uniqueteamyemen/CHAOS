# CHAOS — نتائج الجولة الرسمية متعددة المصادر: IMF

## نتيجة الوصول

الرابط المباشر المفترض لـIMF Direction of Trade (`https://data.imf.org/en/datasets/IMF.STA:DOT`) أعاد صفحة رسمية بعنوان `Page Not Found`. لا يجوز تسجيله كـdataset متاح أو إعادة استخدام endpoint قديم دون اكتشاف المسار الحالي من كتالوج IMF.

## بوابة IMF Data الحالية

المصدر الرسمي: https://data.imf.org/en

توضح الصفحة الحالية أن WEO database يصدر مرتين سنوياً، ويضم national accounts والتضخم والبطالة وميزان المدفوعات والمؤشرات المالية والتجارة للدول والمجموعات، مع بيانات من 1980 إلى الحاضر وتوقعات لمعظم السلاسل. كما تنبه الصفحة إلى أن بعض الدول والمؤشرات والسنوات ناقصة أو غير متاحة. هذه خصائص مهمة للمقارنة مع WDI، لكنها لا تثبت أن Direction of Trade dataset نفسه متاح من الرابط القديم.

## قرار الجولة

1. IMF مصدر رسمي مناسب لجولة مقارنة أعمق، لكن يجب أولاً استخراج dataset identifier الحالي من Data Explorer/Datasets أو وثائق IMF الرسمية.
2. لا تُسجل محاولة الرابط الفاشل كدليل على غياب بيانات IMF؛ تُسجل كـ`endpoint_not_found` فقط.
3. لا تُستخدم بيانات WEO أو projections في Edge تاريخية قبل تثبيت vintage، revision، وhistorical-only cutoff.
4. أي trade data من IMF يجب أن تظل منفصلة عن WDI وWTO وComtrade، مع حفظ التعريف والمنهجية وعدم source averaging.
