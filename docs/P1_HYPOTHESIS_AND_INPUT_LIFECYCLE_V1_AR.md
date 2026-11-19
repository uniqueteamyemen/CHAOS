# P1 — فصل دورة حياة الفرضية عن تصرف إدخال البيانات V1

**الحالة:** عقد/آلية انتقال مستقلة؛ لا تُنشئ Registry ولا تعدّل السجلات القديمة.
**الفرع:** \`fix/p2-2-3-gem-snapshot\`

## الفصل الدلالي الإلزامي

**Hypothesis lifecycle** يصف مصير فرضية بحثية محددة الإصدار:
\`CANDIDATE → UNDER_TEST → DISCOVERED → VALIDATION_PENDING → VALIDATED\`
مع مسارات فشل صريحة إلى \`REJECTED\` أو \`UNRESOLVED\`، وإغلاق رفضها عبر \`LOCKED_REJECTED\`.

**Input disposition** يصف أهلية مدخل/دليل في مسار التنفيذ:
\`ACCEPT\`, \`ABSTAIN\`, \`QUARANTINE\`, \`REJECT\`.

لا يجوز استخدام \`QUARANTINE\` كحالة فرضية، ولا \`LOCKED_REJECTED\` كحالة سجل إدخال. وقد تكون الفرضية صالحة بينما أحد المدخلات محجور، أو يكون المدخل مقبولاً بينما الفرضية نفسها قيد الاختبار.

## قاعدة الإغلاق وإعادة التقييم

- \`REJECTED → LOCKED_REJECTED\` يغلق نتيجة الفرضية ضمن إصدارها وعقدها وEpoch الخاص بها.
- لا يوجد انتقال مباشر من \`LOCKED_REJECTED\` إلى \`UNDER_TEST\` أو \`CANDIDATE\`.
- لا يؤدي تغيير threshold وحده إلى إعادة فتح الفرضية.
- إذا تغيّر مصدر البيانات أو vintage أو تعريف المجال أو عقد الرصد أو النظام الخارجي، يُنشأ إصدار فرضية جديد (\`hypothesis_version + 1\`) بحقل \`supersedes\` ودليل \`trigger_shift\`.
- السجل القديم لا يُعدّل. الإصدار الجديد يبدأ \`CANDIDATE\` ولا يرث حالة التحقق السابقة تلقائياً.

## حد التكامل

هذه آلية عقدية ومساعد انتقال فقط. لا تنشئ قاعدة بيانات أو Registry جديداً. عند P1.5 تُربط الحقول بالسجل/الـPattern Registry القائم بعد جرد مساراته الفعلية. يظل \`residual_event_v1\` القديم دون تعديل.

## الاختبار

\`\`\`bash
python -m unittest discover -s tests/observation_foundation -v
\`\`\`
