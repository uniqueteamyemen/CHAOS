# ملاحظة مصدر البيانات الزلزالية — USGS v1

اعتمدت عقد النقل على **USGS Earthquake Catalog FDSN Event Web Service**. توثق USGS أن الخدمة تتيح استعلامات مخصصة عبر `query`، وتدعم `format=geojson`، وقيود الزمن `starttime/endtime`، والمربع الجغرافي عبر `minlatitude/maxlatitude/minlongitude/maxlongitude`، وعتبة `minmagnitude`، والترتيب `orderby=time-asc`.[^1] كما توضح وثائق GeoJSON أن الناتج FeatureCollection وأن كل feature يحمل `mag` و`time` و`geometry.coordinates` التي تتضمن longitude وlatitude وdepth، إضافة إلى معرف الحدث.[^2]

جرى تثبيت المصدر والنطاق والعتبة والفترة في `experimental_contracts/EVENT_PATH_SEISMIC_TRANSFER_CONTRACT_V1.json` قبل تنفيذ الاستعلام. لا يستخدم الاختبار الزلزالي أي تعديل لتعريف النموذج الاقتصادي أو لاختيار window width أو train size.

## المراجع

[^1]: [USGS API Documentation — Earthquake Catalog](https://earthquake.usgs.gov/fdsnws/event/1/)
[^2]: [USGS GeoJSON Summary Format](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php)
