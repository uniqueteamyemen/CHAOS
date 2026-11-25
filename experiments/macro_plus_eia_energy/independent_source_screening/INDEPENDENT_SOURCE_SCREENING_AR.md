# فحص المصادر المستقلة — 26 أغسطس 2026

## Penn World Table 11.0

المصدر الرسمي: https://www.rug.nl/ggdc/productivity/pwt/?lang=en

تذكر الصفحة الرسمية أن PWT 11.0 يغطي 185 دولة بين 1950 و2023، وأن الوصول الكامل يتم عبر Dataverse، DOI: https://doi.org/10.34894/FABVLR. الترخيص Creative Commons Attribution 4.0 International. يتضمن المتغيرات RGDPNA وRGDPo وRGDPe وpopulation وغيرها، مع تنبيه إلى أن متغيرات GDP الحقيقية بالدولار وليست per-capita، ويمكن استخدام population لبناء per-capita عند الحاجة. الصفحة منشورة في 7 أكتوبر 2025 وآخر تعديل معلن 19 مارس 2026.

PWT مرشح مستقل مناسب لاختبار الصيغة على مصدر نمو/ناتج مختلف عن WDI، لكنه يغطي حتى 2023 فقط، كما أن تعريفه ومستويات PPP قد تختلف عن WDI. لذلك يجب أن يُعامل كـexternal replication panel لا كامتداد مباشر للمصفوفة الحالية.

## United Nations National Accounts AMA

المصدر الرسمي: https://unstats.un.org/unsd/snaama/

تذكر الصفحة أن قاعدة National Accounts Main Aggregates تقدم جداول حسابات قومية سنوية من 1970 فصاعداً لأكثر من 200 دولة/منطقة، وتُحدّث سنوياً. تعتمد على بيانات الحسابات القومية الرسمية التي تبلغها الدول، لكن عند غياب مجموعة كاملة تُستخدم تقديرات وإجراءات استكمال؛ وتعرض الصفحة أن طرق ومصادر التقدير يجب أخذها في الاعتبار. يتم توفير metadata حسب البلد.

AMA مرشح مستقل آخر، لكنه ليس خاماً رسمياً بالكامل لكل observation بسبب وجود estimation procedures في بعض السلاسل. إذا استُخدم، يجب الاحتفاظ بمعلومات estimation/methodology وعدم دمجها صامتاً مع PWT أو WDI.

## قرار screening الأولي

أولوية التجربة الأولى: PWT 11.0 لأنه يقدم سلسلة ناتج/دخل مستقلة واسعة زمنياً، مع توثيق وتعريفات ومصدر وصول واضح. AMA يبقى مسار cross-check مستقل لاحقاً، وليس بديلاً مدمجاً في نفس اللوحة قبل تدقيق metadata.

لا يوجد تنزيل أو تشغيل نموذج في هذه المذكرة؛ هذه مرحلة screening فقط.

## تنزيل AMA الفعلي

تم تنزيل ملفين من صفحة التنزيل الرسمية https://unstats.un.org/unsd/snaama/downloads:

- Growth Rate of GDP، الرابط الرسمي https://unstats.un.org/unsd/amaapi/api/file/16، SHA-256=`b707760b18cc63bc97d546ed3d67f40ca0f49e0607493380ee590bec0f053e78`.
- Exchange Rates and Population، الرابط الرسمي https://unstats.un.org/unsd/amaapi/api/file/30، SHA-256=`e15fcbcf64e74016b3be63d6a0a1d837fe570287867e2a3d9ac0bec89c91bc6e`.

اُستخرجت منهما صفوف `Gross Domestic Product (GDP)` و`Population` فقط إلى staging مشتق، مع إبقاء الخام دون تعديل. اللوحة الناتجة 12,100 صفاً، 220 CountryID، وتغطي 1970–2024 سنوياً. لم تُستخدم 2020–2024 في replication الحالية لتجنب إعادة استخدام نافذة locked test السابقة، رغم وجودها في المصدر.

الصفحة الرسمية للـAMA تذكر أن قاعدة Main Aggregates تغطي من 1970 لأكثر من 200 دولة/منطقة وتُحدّث سنوياً، وأن بعض السلاسل قد تستخدم إجراءات تقدير عند نقص البيانات الرسمية. لذلك تعالج CHAOS AMA كمصدر مستقل موثق مع metadata، لا كحقيقة خام موحدة لكل observation.

## UCDP كمسار domain مستقل

صفحة مركز تنزيل UCDP الرسمي https://ucdp.uu.se/downloads/ تعلن أن UCDP GED Global version 26.1 يغطي أحداث العنف المنظم الفردية، مع إحداثيات جغرافية دقيقة وزمن مفصل إلى أيام منفردة. الملفات متاحة CSV وExcel وCodebook، وكل datasets مجانية تحت CC BY 4.0 مع اشتراط الاستشهاد.

هذا المصدر مناسب للمرحلة متعددة المجالات، لكن لا يجوز تحويل GED إلى قيمة سنوية وإدخالها في لوحة AMA أو WDI. إذا استُخدم، سيبقى event-native: تُحفظ event_date والمكان والوفيات ونوع العنف كما هي، ويُعرّف الربط مع الحالة الاقتصادية بعقد صريح على مستوى الحدث أو origin، لا بتجميع سنوي قسري.

الاستشهادات الرسمية المعلنة تشمل Davies, Pettersson and Öberg (2026) وSundberg and Melander (2013). لا يوجد تنزيل لـUCDP في هذه المذكرة حتى الآن؛ هذه نتيجة screening قبل الاكتساب.

## تنزيل UCDP الفعلي

تم تنزيل UCDP Organized Violence Country-Year 26.1 من الرابط الرسمي https://ucdp.uu.se/downloads/organizedviolencecy/organizedviolencecy-261-csv.zip. هذا ملف سنوي أصلي، واستُخدم في cross-domain replication مع AMA دون تحويل GED اليومي.

كما تم تنزيل UCDP GED 26.1 بصيغة CSV المضغوطة من https://ucdp.uu.se/downloads/ged/ged261-csv.zip مع codebook. بقي GED event-native خارج cross-domain الحالي ولم يُستخدم لبناء outcome سنوي. هذا الفصل مقصود حتى لا نخلط event frequency مع Country-Year frequency.
