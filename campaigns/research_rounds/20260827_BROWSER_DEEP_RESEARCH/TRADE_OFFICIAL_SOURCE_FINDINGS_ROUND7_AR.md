# CHAOS — IMF Data: اكتشاف الكتالوج الحالي عبر المتصفح

المصدر الرسمي: https://data.imf.org/en/datasets

أظهر كتالوج IMF الحالي `106` dataset في نتائج الصفحة الأولى. من بينها:

- Balance of Payments (BOP): annual وquarterly، ويشمل goods/services account والحسابات الخارجية.
- International Trade in Goods (ITG): annual وmonthly وquarterly، وتعريفه يشمل السلع التي تدخل أو تخرج من الإقليم الاقتصادي مع استثناءات النقل/الإدخال المؤقت.
- National Economic Accounts Annual Data: annual.
- CPI World and Country Aggregates: monthly.
- International Liquidity: annual/monthly/quarterly.
- MFS وغيرها من الإحصاءات النقدية والمالية.

توضح الصفحة أن datasets الحديثة تحمل publication date مثل Aug 26, 2026، وتتيح Metadata وSee Vintages وDownload. هذا يثبت أن IMF لديه مسار حالي أقوى من رابط DOT القديم الذي أعاد Page Not Found، لكنه لا يثبت بعد dataset ID أو ملف تنزيل ITG الفعلي.

## قرار الجولة

1. يجب استخدام كتالوج IMF الحالي لا endpoint DOT القديم عند تصميم الجولة التالية.
2. ITG مرشح رسمي مباشر للتجارة متعدد التواتر، ويمكن مقارنته مع WDI/WTO/Comtrade بعد تثبيت vintage وcoverage.
3. لا تُمزج annual/monthly/quarterly؛ كل تواتر يبقى في DomainState منفصل.
4. لا تُستخدم بيانات IMF projections أو vintages غير محددة في Edge تاريخية.
5. الحالة الحالية: `official_dataset_catalog_confirmed; ITG_download_pending_metadata_and_file_verification`.
