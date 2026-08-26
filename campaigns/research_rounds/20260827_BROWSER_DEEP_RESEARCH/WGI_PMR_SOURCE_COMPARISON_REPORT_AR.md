# CHAOS — مقارنة مصدرية WGI–PMR

## الغرض

هذه ليست تجربة انتقال زمني ولا اختباراً سببياً. الغرض هو فحص ما إذا كان قياسان مؤسسيان رسميان يلتقيان في نفس السنوات والكيانات، مع إبقاء تعريف كل مصدر واتجاه قياسه منفصلاً.

## التقاطع الفعلي

تمت المطابقة على `entity_id + source year` فقط، دون interpolation. شمل التقاطع 47 كياناً وأربع موجات PMR: 1998 و2003 و2008 و2013. بلغ مصدر WGI المستخدم 32,403 حالة، وبلغ PMR Archive 4,134 حالة و29 مؤشراً.

## النتيجة الوصفية

ارتبط WGI Regulatory Quality سلبياً مع PMR Product Market Regulation في التقاطع: Pearson=`-0.720766` وSpearman=`-0.656137` عبر 144 صفاً. وهذا متسق اتجاهياً مع اختلاف تعريف القياس: بعض PMR indicators تقيس الحواجز/التقييد، بينما WGI Regulatory Quality يقيس جودة تنظيمية وفق مقياس مختلف. ظهرت ارتباطات سالبة أيضاً مع BTI وBTE وTRD وTRF، لكنها لا تثبت تطابقاً أو آلية سببية.

| WGI dimension | PMR indicator | rows | entities | Pearson | Spearman |
|---|---:|---:|---:|---:|---:|
| Regulatory Quality | PMR | 144 | 47 | -0.720766 | -0.656137 |
| Regulatory Quality | BTI | 145 | 47 | -0.649115 | -0.544822 |
| Regulatory Quality | BTE | 144 | 47 | -0.555767 | -0.502062 |
| Regulatory Quality | TRD | 145 | 47 | -0.518299 | -0.515061 |
| Regulatory Quality | TRF | 145 | 47 | -0.530346 | -0.402371 |
| Government Effectiveness | PMR | 144 | 47 | -0.649317 | -0.561462 |

## قرار الحوكمة

تُسجل النتيجة كـ`descriptive_source_concordance_only`. لا تُضاف إلى TransitionEvidence كحافة، ولا تدخل Evidence Graph بوزن موجب، ولا تُستخدم لاستخراج policy shock أو leader-specific deviation. قيمتها العملية هي تنبيه الـadapter والـComposer إلى أن اختلاف اتجاه القياس والتعريفات يجب أن يظل ظاهراً بدلاً من source averaging أو بناء composite مؤسسي مخفي.
