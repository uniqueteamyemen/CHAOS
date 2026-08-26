# CHAOS — IMF Data: اكتشاف datasets التجارة الحالية

المصدر الرسمي: https://data.imf.org/en/datasets?q=International%20Trade%20in%20Goods

بعد استخدام بحث الكتالوج الرسمي ظهر `Results 1-4 of 4`، ومن بينها:

1. **International Trade in Goods (ITG)**، منشور 26 August 2026، بتواترات Annual/Monthly/Quarterly، ويعرّف تجارة السلع التي تدخل أو تخرج من الإقليم الاقتصادي.
2. **International Trade in Goods (by partner country) (IMTS)**، منشور 6 August 2026، وهو الاسم الحالي للبيانات التي كانت تُعرف سابقاً بـDirection of Trade Statistics (DOTS)، ويقدم صادرات وواردات السلع مفصلة حسب الشركاء التجاريين، بتواترات Annual/Monthly/Quarterly.
3. **Trade in Low Carbon Technology Goods (TEG)**، annual، مع تدفقات ثنائية لسلع التكنولوجيا منخفضة الكربون.
4. **Macroeconomic Climate Indicators Dashboard**، منصة متطورة تضم مؤشرات مناخية وما يرتبط بالتجارة البيئية، وبعضها تقديرات IMF staff؛ لا يُعامل كقياس خام متجانس.

## قرار الجولة

هذا يغير تقييم IMF السابق: endpoint `IMF.STA:DOT` القديم غير صالح، لكن dataset الحالي IMTS متاح في كتالوج IMF كخلف رسمي لـDOTS. يجب فتح صفحة IMTS واستخراج رابط metadata/download/vintage قبل أي acquisition.

ITG وIMTS لا يُدمجان مع WDI أو Comtrade أو WTO تلقائياً. ITG aggregate goods، وIMTS partner-country، ولكل منهما تواتر مستقل وإصدار حديث. لا تُستخدم projections أو staff estimates كحقائق خام دون وسمها.

الحالة: `official_current_trade_datasets_discovered; IMTS_download_and_metadata_pending`.
