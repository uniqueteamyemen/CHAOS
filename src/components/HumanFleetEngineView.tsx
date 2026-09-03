// src/components/HumanFleetEngineView.tsx
import React, { useState, useMemo } from 'react';
import {
  Activity,
  Layers,
  Sliders,
  Calendar,
  Sparkles,
  Info,
  Shield,
  Zap,
  RotateCcw,
  CheckCircle2,
  AlertOctagon,
  Flame,
  Globe2
} from 'lucide-react';
import {
  computeFleetCalculus,
  computeMultiYearTrajectory,
  DEFAULT_CALCULUS_PARAMS,
  CalculusParameters,
  HISTORICAL_CHECKPOINTS
} from '../utils/humanImpactCalculus';
import { FleetSeriesItem } from '../data/fleet50Series';
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid
} from 'recharts';

export const HumanFleetEngineView: React.FC = () => {
  const [params, setParams] = useState<CalculusParameters>(DEFAULT_CALCULUS_PARAMS);
  const [selectedLayer, setSelectedLayer] = useState<'all' | 'nature' | 'infrastructure' | 'human_system'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeSeriesDetail, setActiveSeriesDetail] = useState<FleetSeriesItem | null>(null);

  // Recompute fleet snapshot for selected year
  const snapshot = useMemo(() => computeFleetCalculus(params), [params]);

  // Compute multi-year trajectory for charts and backtesting
  const trajectory = useMemo(() => computeMultiYearTrajectory(params), [
    params.natureVulnerabilityCoupling,
    params.humanDecisionCoupling,
    params.bufferingShieldPower,
    params.reboundCostTax
  ]);

  // Filtered series list
  const filteredItems = useMemo(() => {
    return snapshot.items.filter((item) => {
      const matchLayer = selectedLayer === 'all' || item.series.layer === selectedLayer;
      const matchSearch =
        searchQuery.trim() === '' ||
        item.series.nameAr.includes(searchQuery) ||
        item.series.nameEn.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.series.source.toLowerCase().includes(searchQuery.toLowerCase());
      return matchLayer && matchSearch;
    });
  }, [snapshot.items, selectedLayer, searchQuery]);

  const resetToDefaults = () => {
    setParams(DEFAULT_CALCULUS_PARAMS);
  };

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Banner: Core Scientific Mission */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none"></div>
        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                <Globe2 className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                  مختبر الأثر البشري للـ 50 سلسلة المرجعية
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 font-mono">
                    Non-Absolute Human Calculus
                  </span>
                </h1>
                <p className="text-sm text-slate-400">
                  معايرة السلاسل الزمنية المتنافرة على مسطرة موحدة: «أثرها الممتد على الكائن البشري خيراً وشراً دون أحكام مطلقة».
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={resetToDefaults}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>إعادة ضبط المعاملات للأساس</span>
            </button>
          </div>
        </div>
      </div>

      {/* Year Selector / Historical Timeline Slider */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 text-sm font-semibold text-slate-200">
            <Calendar className="w-4 h-4 text-cyan-400" />
            <span>محطة الفحص الزمني المختارة (Target Benchmark Year):</span>
            <span className="text-lg font-mono font-bold text-cyan-400 px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-800">
              {params.targetYear}
            </span>
          </div>
          <span className="text-xs text-slate-400 font-mono hidden sm:inline-block">
            نقطة الارتكاز المركزية: عام 2008 (سنة التقاطع)
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
          {HISTORICAL_CHECKPOINTS.map((cp) => {
            const isSelected = params.targetYear === cp.year;
            return (
              <button
                key={cp.year}
                onClick={() => setParams({ ...params, targetYear: cp.year })}
                className={`p-3 rounded-lg text-right transition-all flex flex-col justify-between border ${
                  isSelected
                    ? 'bg-cyan-950/70 border-cyan-500/80 shadow-md shadow-cyan-950/50 ring-1 ring-cyan-500/40'
                    : 'bg-slate-950/60 border-slate-800/80 hover:bg-slate-800/50 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className={`text-base font-bold font-mono ${isSelected ? 'text-cyan-300' : 'text-slate-200'}`}>
                    {cp.year}
                  </span>
                  {cp.year === 2008 && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-mono">
                      الالتقاء
                    </span>
                  )}
                </div>
                <span className="text-[11px] text-slate-400 mt-1 line-clamp-1">
                  {cp.labelAr.split(':')[1] || cp.labelAr}
                </span>
              </button>
            );
          })}
        </div>

        {/* Current Year Historical Context Callout */}
        <div className="bg-slate-950/70 border border-slate-800/80 rounded-lg p-3 text-xs flex items-start space-x-3">
          <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold text-slate-300">
              سياق عام {params.targetYear}:
            </span>
            <p className="text-slate-400">
              {HISTORICAL_CHECKPOINTS.find((c) => c.year === params.targetYear)?.eventAr}
            </p>
          </div>
        </div>
      </div>

      {/* Key Metric Pulse Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Metric 1: Net Human Pulse */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>صافي النبض البشري (Net Pulse)</span>
            <Activity className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="my-3">
            <div className={`text-3xl font-bold font-mono ${
              snapshot.netHumanPulse > 0 ? 'text-emerald-400' : snapshot.netHumanPulse < 0 ? 'text-rose-400' : 'text-slate-300'
            }`}>
              {snapshot.netHumanPulse > 0 ? `+${snapshot.netHumanPulse}` : snapshot.netHumanPulse}
            </div>
            <span className="text-xs text-slate-500">
              {snapshot.netHumanPulse > 0 ? 'كفة التمكين والبناء هي الغالبة' : 'كفة الضغط والمعاناة هي الغالبة'}
            </span>
          </div>
          <div className="text-[11px] text-slate-400 border-t border-slate-800/80 pt-2 flex justify-between">
            <span>🟢 فائدة: {snapshot.strainDistribution.positiveCount}</span>
            <span>🔴 ضغط: {snapshot.strainDistribution.negativeCount}</span>
            <span>⚪ محايد: {snapshot.strainDistribution.neutralCount}</span>
          </div>
        </div>

        {/* Metric 2: Total Turbulence Energy */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>طاقة الاضطراب الكلية (|Turbulence|)</span>
            <Flame className="w-4 h-4 text-amber-400" />
          </div>
          <div className="my-3">
            <div className="text-3xl font-bold font-mono text-amber-400">
              {snapshot.totalTurbulenceEnergy}
            </div>
            <span className="text-xs text-slate-500">
              مجموع القوى المتفاعلة (شدة إعادة التشكيل الحضاري)
            </span>
          </div>
          <div className="text-[11px] text-slate-400 border-t border-slate-800/80 pt-2">
            درجة التحول الشامل لعام {params.targetYear}
          </div>
        </div>

        {/* Metric 3: Layer Decomposition */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>توزيع ثقل الطبقات الثلاث</span>
            <Layers className="w-4 h-4 text-purple-400" />
          </div>
          <div className="my-2 space-y-1.5 text-xs font-mono">
            <div className="flex items-center justify-between">
              <span className="text-blue-400">الطبقة 1 (طبيعة قاهرة):</span>
              <span className="font-bold">{snapshot.layerShares.naturePercentage}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-emerald-400">الطبقة 2 (تمكين وبنية):</span>
              <span className="font-bold">{snapshot.layerShares.infrastructurePercentage}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-rose-400">الطبقة 3 (صنع بشري):</span>
              <span className="font-bold">{snapshot.layerShares.humanSystemPercentage}%</span>
            </div>
          </div>
          <div className="w-full bg-slate-950 rounded-full h-2 flex overflow-hidden border border-slate-800">
            <div style={{ width: `${snapshot.layerShares.naturePercentage}%` }} className="bg-blue-500 h-full"></div>
            <div style={{ width: `${snapshot.layerShares.infrastructurePercentage}%` }} className="bg-emerald-500 h-full"></div>
            <div style={{ width: `${snapshot.layerShares.humanSystemPercentage}%` }} className="bg-rose-500 h-full"></div>
          </div>
        </div>

        {/* Metric 4: Shield & Rebound Multipliers */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>درع العصر وضريبة الارتداد</span>
            <Shield className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="my-2 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">درع الصد التكنولوجي B(t):</span>
              <span className="font-mono font-bold text-cyan-300">×{snapshot.bufferingShield}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">ضريبة الارتداد والتكلفة Γ(t):</span>
              <span className="font-mono font-bold text-amber-300">×{snapshot.reboundMultiplier}</span>
            </div>
          </div>
          <div className="text-[11px] text-slate-500 border-t border-slate-800/80 pt-2">
            كلما تقدم الزمن زادت قوة الدرع وزادت معه تكلفة الصيانة والديون
          </div>
        </div>
      </div>

      {/* Trajectory Timeline Chart (Multi-Decade Human Pulse & Turbulence) */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-4">
          <div>
            <h3 className="text-base font-bold text-slate-200 flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              <span>المسار التاريخي لنبض الإنسانية وطاقة التحول (1973 - 2024)</span>
            </h3>
            <p className="text-xs text-slate-400">
              تتبع كيف أثّرت المحطات السبع على ميزان البشرية عبر العقود مع توضيح الفواصل الزمنية (Δt)
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-cyan-400"></div>
              <span className="text-slate-300">صافي النبض (Net Pulse)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded bg-amber-500/60"></div>
              <span className="text-slate-300">طاقة الاضطراب (Turbulence)</span>
            </div>
          </div>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={trajectory} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="year" stroke="#64748b" tick={{ fontSize: 12 }} />
              <YAxis stroke="#64748b" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                labelStyle={{ color: '#94a3b8', fontWeight: 'bold' }}
              />
              <Area
                type="monotone"
                dataKey="totalTurbulenceEnergy"
                name="طاقة الاضطراب الكلية"
                fill="#f59e0b"
                fillOpacity={0.15}
                stroke="#f59e0b"
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="netHumanPulse"
                name="صافي النبض البشري"
                stroke="#06b6d4"
                strokeWidth={3}
                dot={{ r: 5, fill: '#06b6d4' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Historical Inter-Cycle Table (Delta t Analysis) */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-xs font-mono pt-2">
          {trajectory.slice(1).map((t, idx) => (
            <div key={t.year} className="bg-slate-950/60 border border-slate-800/80 rounded p-2.5">
              <div className="flex items-center justify-between text-slate-400">
                <span>{trajectory[idx].year} ← {t.year}</span>
                <span className="text-cyan-400 font-bold">Δt = {t.deltaYearsFromPrior} سنوات</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-1 truncate">
                {t.labelAr.split(':')[1] || t.labelAr}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Interactive Calculus Tuning Panel */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-lg space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <Sliders className="w-5 h-5 text-cyan-400" />
            <h3 className="text-base font-bold text-slate-200">
              معايرة بارامترات الصيغة الرياضية (Calculus Calibration Sliders)
            </h3>
          </div>
          <span className="text-xs text-slate-400">
            اختبار حساسية النموذج لفرضيات الفيزياء والتحكم البشري
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Slider 1: Nature Coupling */}
          <div className="space-y-2 bg-slate-950/60 p-4 rounded-lg border border-slate-800/80">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-300">وزن هشاشة البشر أمام الطبيعة</span>
              <span className="font-mono text-cyan-400 font-bold">{params.natureVulnerabilityCoupling.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.05"
              max="0.50"
              step="0.01"
              value={params.natureVulnerabilityCoupling}
              onChange={(e) => setParams({ ...params, natureVulnerabilityCoupling: parseFloat(e.target.value) })}
              className="w-full accent-cyan-400 h-1.5 bg-slate-800 rounded cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              يقيس مدى تحول هزة الطبيعة إلى ضرر إنساني (الزلزال أو الشمس).
            </p>
          </div>

          {/* Slider 2: Human Decision Coupling */}
          <div className="space-y-2 bg-slate-950/60 p-4 rounded-lg border border-slate-800/80">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-300">وزن المحرك المصنوع بشرياً</span>
              <span className="font-mono text-rose-400 font-bold">{params.humanDecisionCoupling.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.50"
              max="1.50"
              step="0.05"
              value={params.humanDecisionCoupling}
              onChange={(e) => setParams({ ...params, humanDecisionCoupling: parseFloat(e.target.value) })}
              className="w-full accent-rose-400 h-1.5 bg-slate-800 rounded cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              ثقل الصدمات النابعة من قرارات البشر والفقاعات المالية.
            </p>
          </div>

          {/* Slider 3: Buffering Shield Power */}
          <div className="space-y-2 bg-slate-950/60 p-4 rounded-lg border border-slate-800/80">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-300">قوة امتصاص درع العصر B(t)</span>
              <span className="font-mono text-emerald-400 font-bold">{params.bufferingShieldPower.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.2"
              max="2.0"
              step="0.1"
              value={params.bufferingShieldPower}
              onChange={(e) => setParams({ ...params, bufferingShieldPower: parseFloat(e.target.value) })}
              className="w-full accent-emerald-400 h-1.5 bg-slate-800 rounded cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              كفاءة التكنولوجيا وشبكات الكهرباء في حماية البشر من الفناء.
            </p>
          </div>

          {/* Slider 4: Rebound Cost Tax */}
          <div className="space-y-2 bg-slate-950/60 p-4 rounded-lg border border-slate-800/80">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-300">ضريبة الارتداد والتكلفة Γ(t)</span>
              <span className="font-mono text-amber-400 font-bold">{params.reboundCostTax.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="2.0"
              step="0.1"
              value={params.reboundCostTax}
              onChange={(e) => setParams({ ...params, reboundCostTax: parseFloat(e.target.value) })}
              className="w-full accent-amber-400 h-1.5 bg-slate-800 rounded cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              التكلفة العكسية للتدخل البشري (الديون والتضخم والآثار الجانبية).
            </p>
          </div>
        </div>
      </div>

      {/* The 50 Series Data Matrix View */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl shadow-lg overflow-hidden space-y-4 p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <h3 className="text-base font-bold text-slate-200 flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              <span>مصفوفة الـ 50 سلسلة المحسوبة (Fleet 50 Evaluated Matrix)</span>
            </h3>
            <p className="text-xs text-slate-400">
              النتائج المسقطة بالصيغة الرياضية لسنة {params.targetYear} ({filteredItems.length} سلسلة ظاهرة)
            </p>
          </div>

          {/* Layer Filter Pills & Search */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex bg-slate-950 rounded-lg p-1 border border-slate-800 text-xs">
              <button
                onClick={() => setSelectedLayer('all')}
                className={`px-3 py-1 rounded transition-colors ${
                  selectedLayer === 'all' ? 'bg-cyan-500/20 text-cyan-300 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                الكل (50)
              </button>
              <button
                onClick={() => setSelectedLayer('nature')}
                className={`px-3 py-1 rounded transition-colors ${
                  selectedLayer === 'nature' ? 'bg-blue-500/20 text-blue-300 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                طبيعة قاهرة (10)
              </button>
              <button
                onClick={() => setSelectedLayer('infrastructure')}
                className={`px-3 py-1 rounded transition-colors ${
                  selectedLayer === 'infrastructure' ? 'bg-emerald-500/20 text-emerald-300 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                تمكين وبنية (20)
              </button>
              <button
                onClick={() => setSelectedLayer('human_system')}
                className={`px-3 py-1 rounded transition-colors ${
                  selectedLayer === 'human_system' ? 'bg-rose-500/20 text-rose-300 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                صنع بشري (20)
              </button>
            </div>

            <input
              type="text"
              placeholder="بحث في السلاسل..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        {/* Table of 50 Series */}
        <div className="overflow-x-auto">
          <table className="w-full text-right text-xs">
            <thead className="bg-slate-950 text-slate-400 font-mono border-b border-slate-800">
              <tr>
                <th className="py-3 px-3">#</th>
                <th className="py-3 px-3">السلسلة المستقلة</th>
                <th className="py-3 px-3">الطبقة</th>
                <th className="py-3 px-3">توليد بشري (γ)</th>
                <th className="py-3 px-3">امتداد الأثر (τ)</th>
                <th className="py-3 px-3">الضغط الخام</th>
                <th className="py-3 px-3">الأثر البشري المحسوب (Score)</th>
                <th className="py-3 px-3 text-center">التصنيف</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filteredItems.map((item, idx) => {
                const s = item.series;
                const isPositive = item.finalScore > 0.08;
                const isNegative = item.finalScore < -0.08;

                return (
                  <tr
                    key={s.id}
                    onClick={() => setActiveSeriesDetail(s)}
                    className="hover:bg-slate-800/40 transition-colors cursor-pointer"
                  >
                    <td className="py-2.5 px-3 text-slate-500">{idx + 1}</td>
                    <td className="py-2.5 px-3">
                      <div className="font-sans font-semibold text-slate-200">{s.nameAr}</div>
                      <div className="text-[10px] text-slate-400">{s.source}</div>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`text-[10px] px-2 py-0.5 rounded font-sans ${
                        s.layer === 'nature'
                          ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                          : s.layer === 'infrastructure'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}>
                        {s.layer === 'nature' ? 'طبيعة' : s.layer === 'infrastructure' ? 'تمكين' : 'صنع بشري'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-300">{(s.gamma * 100).toFixed(0)}%</td>
                    <td className="py-2.5 px-3 text-slate-300">{item.tau.toFixed(1)} سنة</td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {item.rawStress > 0 ? `+${item.rawStress}` : item.rawStress}
                    </td>
                    <td className="py-2.5 px-3 font-bold">
                      <span className={isPositive ? 'text-emerald-400' : isNegative ? 'text-rose-400' : 'text-slate-400'}>
                        {item.finalScore > 0 ? `+${item.finalScore}` : item.finalScore}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {isPositive ? (
                        <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400">
                          <CheckCircle2 className="w-3.5 h-3.5" /> 🟢 فائدة
                        </span>
                      ) : isNegative ? (
                        <span className="inline-flex items-center gap-1 text-[11px] text-rose-400">
                          <AlertOctagon className="w-3.5 h-3.5" /> 🔴 مشكلة
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                          ⚪ غير محسوم
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Modal for Selected Series */}
      {activeSeriesDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-xl w-full p-6 space-y-4 shadow-2xl relative">
            <div className="flex items-start justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 font-mono">
                  {activeSeriesDetail.id}
                </span>
                <h4 className="text-lg font-bold text-slate-100 mt-1">
                  {activeSeriesDetail.nameAr}
                </h4>
                <p className="text-xs text-slate-400">{activeSeriesDetail.nameEn}</p>
              </div>
              <button
                onClick={() => setActiveSeriesDetail(null)}
                className="text-slate-400 hover:text-slate-200 text-sm font-mono px-2 py-1 bg-slate-800 rounded"
              >
                ✕ إغلاق
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <p className="text-slate-300 leading-relaxed">
                {activeSeriesDetail.descriptionAr}
              </p>

              <div className="grid grid-cols-2 gap-2 font-mono bg-slate-950 p-3 rounded-lg border border-slate-800">
                <div>
                  <span className="text-slate-500">المصدر:</span>{' '}
                  <span className="text-slate-300">{activeSeriesDetail.source}</span>
                </div>
                <div>
                  <span className="text-slate-500">وحدة القياس:</span>{' '}
                  <span className="text-slate-300">{activeSeriesDetail.unit}</span>
                </div>
                <div>
                  <span className="text-slate-500">نسبة الصنع البشري (γ):</span>{' '}
                  <span className="text-cyan-400 font-bold">{(activeSeriesDetail.gamma * 100).toFixed(0)}%</span>
                </div>
                <div>
                  <span className="text-slate-500">الامتداد الزمني المعتاد (τ):</span>{' '}
                  <span className="text-amber-400 font-bold">{activeSeriesDetail.defaultDurationYears} سنوات</span>
                </div>
              </div>

              {/* 2008 specific event snapshot */}
              <div className="bg-cyan-950/30 border border-cyan-800/60 rounded-lg p-3 space-y-1">
                <span className="font-bold text-cyan-300 font-mono">
                  حدث سنة التقاطع (2008 Snapshot):
                </span>
                <p className="text-slate-300">
                  {activeSeriesDetail.snapshot2008.eventDescriptionAr}
                </p>
                <div className="flex gap-4 text-[11px] font-mono text-slate-400 pt-1">
                  <span>القيمة المسجلة: {activeSeriesDetail.snapshot2008.rawValue}</span>
                  <span>الامتداد المشهود: {activeSeriesDetail.snapshot2008.observedDurationYears} سنة</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
