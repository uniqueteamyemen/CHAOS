import React from 'react';
import { ShieldAlert, Database, FileCheck2, AlertCircle } from 'lucide-react';

export const ModelBenchmarksView: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center space-x-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-100">سجل النزاهة والحوكمة: حظر المحاكاة المصطنعة</h2>
            <p className="text-xs text-slate-400 font-mono">AGENTS.md Compliance & Verification Audit</p>
          </div>
        </div>

        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-5 mb-6 text-amber-200">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div className="text-sm space-y-2">
              <p className="font-semibold text-amber-300">إشعار الالتزام بميثاق النزاهة (Rule 1 & 2):</p>
              <p className="text-slate-300 text-xs leading-relaxed">
                تم استبعاد مصفوفات تقييمات نماذج (TFT / Baselines) وأوزان المتغيرات المصطنعة التي لم يتم تدريبها أو احتسابها عبر تشغيل فعلي داخل الحاوية.
                عملاً بالمادة 1 والمادة 4: <strong>"لا تُعتبر النتيجة حقيقية إلا إذا أمكن تتبعها من: المصدر ← البيانات ← المعالجة ← الحساب ← التنفيذ ← النتيجة... وإذا لم يكن الدليل كافياً، فالنتيجة الصحيحة هي: لا توجد أدلة كافية لإثبات النتيجة."</strong>
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4">
            <span className="text-xs font-mono text-slate-400">حالة النماذج التنبؤية</span>
            <div className="mt-2 flex items-baseline justify-between">
              <h3 className="text-lg font-bold font-mono text-amber-400">NON-EXECUTED</h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                PROHIBITED ESTIMATE
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              لا توجد أوزان أو دقة تنبؤ مقدرة؛ التحليل مقصور على الملاحظات الحقيقية الموثقة.
            </p>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4">
            <span className="text-xs font-mono text-slate-400">السلاسل الزمنية الخام الموثقة</span>
            <div className="mt-2 flex items-baseline justify-between">
              <h3 className="text-lg font-bold font-mono text-emerald-400">54+ YEARS GOVERNED</h3>
              <FileCheck2 className="w-5 h-5 text-emerald-400" />
            </div>
            <p className="mt-2 text-xs text-slate-400">
              بيانات البنك الدولي، FRED، WDC-SILSO، ومؤشرات الـ 50 كاملة بمصادرها الرسمية.
            </p>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-4">
            <span className="text-xs font-mono text-slate-400">قاطع الدائرة السببي (Circuit Breaker)</span>
            <div className="mt-2 flex items-baseline justify-between">
              <h3 className="text-lg font-bold font-mono text-cyan-400">ACTIVE & ENFORCED</h3>
              <Database className="w-5 h-5 text-cyan-400" />
            </div>
            <p className="mt-2 text-xs text-slate-400">
              يحظر فورياً أي ادعاء بالسببية دون اختبار إحصائي صارم ضد النماذج الصفرية.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
