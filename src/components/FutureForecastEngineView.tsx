import React, { useState, useMemo } from 'react';
import {
  TrendingUp,
  AlertTriangle,
  Layers,
  ShieldCheck,
  Compass,
  Zap,
  Activity,
  Calendar,
  HelpCircle,
  Sliders,
  Sparkles,
  ArrowUpRight,
  ArrowDownRight,
  Filter
} from 'lucide-react';
import {
  runFutureForecastEngine,
  runHistoricalHindcast,
  ForecastScenario,
  FutureForecastEngineResult,
  HindcastTransitionResult
} from '../utils/futureForecastEngine';

export const FutureForecastEngineView: React.FC = () => {
  const [selectedScenario, setSelectedScenario] = useState<ForecastScenario>('baseline');
  const [selectedLayerFilter, setSelectedLayerFilter] = useState<'all' | 'nature' | 'infrastructure' | 'human_system'>('all');
  const [ensembleSize, setEnsembleSize] = useState<number>(1000);
  const [selectedYear, setSelectedYear] = useState<number>(2030);

  // Compute probabilistic forecast
  const forecastData: FutureForecastEngineResult = useMemo(() => {
    return runFutureForecastEngine(selectedScenario, ensembleSize);
  }, [selectedScenario, ensembleSize]);

  // Compute retrospective hindcast verification for historical transitions
  const hindcastResults = useMemo(() => {
    return runHistoricalHindcast();
  }, []);

  // Filter series results
  const filteredSeries = useMemo(() => {
    return forecastData.seriesResults.filter((s) => {
      if (selectedLayerFilter === 'all') return true;
      return s.layer === selectedLayerFilter;
    });
  }, [forecastData, selectedLayerFilter]);

  const currentSnapshot = useMemo(() => {
    return (
      forecastData.fleetSnapshots.find((s) => s.targetYear === selectedYear) ||
      forecastData.fleetSnapshots[forecastData.fleetSnapshots.length - 1]
    );
  }, [forecastData, selectedYear]);

  return (
    <div className="space-y-8" dir="rtl">
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute -top-12 -left-12 w-48 h-48 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 flex items-center gap-1.5">
                <Compass className="w-3.5 h-3.5" />
                <span>MONTE CARLO ENSEMBLE (N = {ensembleSize})</span>
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                قاعدة الانطلاق: 2024 الفعلية
              </span>
            </div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <TrendingUp className="w-7 h-7 text-cyan-400" />
              <span>محرك الاستشراف المستقبلي (Future Forecast Engine: 2025 → 2030)</span>
            </h1>
            <p className="text-sm text-slate-400 mt-1 max-w-3xl leading-relaxed">
              تطبيق الصيغة الهيكلية المحققة ($F_3$) مع نمذجة التراكم الرأسمالي، والتباطؤ الهيكلي للديون (Debt Hysteresis)، وقنوات الثقة الإحصائية (P10 / P50 / P90) عبر مصفوفات الـ 50 سلسلة.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3 text-center min-w-[120px]">
              <span className="text-[11px] text-slate-500 block font-mono">مؤشر الهشاشة الكلي</span>
              <span className="text-lg font-mono font-bold text-cyan-400">
                {forecastData.macroFragilityScore}
              </span>
            </div>
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3 text-center min-w-[120px]">
              <span className="text-[11px] text-slate-500 block font-mono">مخاطر التشعب (Bifurcation)</span>
              <span
                className={`text-sm font-mono font-bold ${
                  forecastData.bifurcationRisk === 'LOW'
                    ? 'text-emerald-400'
                    : forecastData.bifurcationRisk === 'MODERATE'
                    ? 'text-amber-400'
                    : 'text-rose-400'
                }`}
              >
                {forecastData.bifurcationRisk}
              </span>
            </div>
          </div>
        </div>

        {/* AGENTS.md Causal Circuit-Breaker Warning */}
        <div className="mt-4 pt-4 border-t border-slate-800/80 flex items-start gap-2.5 text-xs text-slate-400">
          <ShieldCheck className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <p className="leading-relaxed font-mono">
            <strong className="text-amber-300">ميثاق النزاهة وقاطع الدائرة: </strong>
            {forecastData.causalStatus.disclaimer}
          </p>
        </div>
      </div>

      {/* Scenario and Control Bar */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Scenarios */}
          <div>
            <label className="text-xs font-mono text-slate-400 block mb-2">
              سيناريو المحاكاة المستقبلي (Simulation Scenario):
            </label>
            <div className="flex flex-wrap gap-2">
              {[
                { id: 'baseline', label: 'السيناريو الأساسي المستقر (Baseline Stasis)' },
                { id: 'accelerated_debt', label: 'تسارع أعباء المديونية (Debt Acceleration)' },
                { id: 'green_transition', label: 'تسارع التحول النظيف (Clean Infra Leap)' },
                { id: 'geopolitical_escalation', label: 'تصاعد الصدمات والقرارات (Geopolitical Jumps)' }
              ].map((sc) => (
                <button
                  key={sc.id}
                  onClick={() => setSelectedScenario(sc.id as ForecastScenario)}
                  className={`px-3.5 py-2 rounded-lg text-xs font-medium transition-all ${
                    selectedScenario === sc.id
                      ? 'bg-cyan-500/20 text-cyan-200 border border-cyan-500/50 shadow-sm'
                      : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {sc.label}
                </button>
              ))}
            </div>
          </div>

          {/* Target Horizon Year Selector */}
          <div>
            <label className="text-xs font-mono text-slate-400 block mb-2">
              أفق الاستشراف (Horizon Year):
            </label>
            <div className="flex gap-1.5">
              {forecastData.targetYears.map((yr) => (
                <button
                  key={yr}
                  onClick={() => setSelectedYear(yr)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all ${
                    selectedYear === yr
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/50 font-bold'
                      : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {yr}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Trajectory Snapshot Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Net Human Pulse */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-slate-400">النبض البشري الصافي المتوقع ({selectedYear})</span>
            <Activity className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-cyan-300">
              {currentSnapshot.expectedPulse > 0 ? `+${currentSnapshot.expectedPulse}` : currentSnapshot.expectedPulse}
            </span>
            <span className="text-xs text-slate-500 font-mono">P50 Expected</span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
            <span>مجال الثقة 80%:</span>
            <span className="text-cyan-400">[{currentSnapshot.p10Pulse} → {currentSnapshot.p90Pulse}]</span>
          </div>
        </div>

        {/* Total Turbulence Energy */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-slate-400">طاقة الاضطراب الكلية ({selectedYear})</span>
            <Zap className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-amber-300">
              {currentSnapshot.expectedTurbulence}
            </span>
            <span className="text-xs text-slate-500 font-mono">Turbulence Units</span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono text-slate-400">
            <span>مجال الثقة 80%:</span>
            <span className="text-amber-400">[{currentSnapshot.p10Turbulence} → {currentSnapshot.p90Turbulence}]</span>
          </div>
        </div>

        {/* Structural Layer Distribution */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-slate-400">توزيع طاقة الطبقات ({selectedYear})</span>
            <Layers className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="space-y-2 text-xs font-mono">
            <div className="flex justify-between items-center">
              <span className="text-emerald-400">البنية التحتية (Infra):</span>
              <span className="font-bold text-slate-200">{currentSnapshot.layerShares.infrastructurePercentage}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-purple-400">القرارات البشرية (Decisions):</span>
              <span className="font-bold text-slate-200">{currentSnapshot.layerShares.humanSystemPercentage}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-cyan-400">النظام البيئي (Nature):</span>
              <span className="font-bold text-slate-200">{currentSnapshot.layerShares.naturePercentage}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Trajectory Evolution Across Horizon (2024 to 2030 Table) */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div>
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-cyan-400" />
              <span>المسار الزمني الكلي (Macro Trajectory Path: 2024 → 2030)</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              التدرج السنوي لاصطفاف النبض البشري الصافي وطاقة الاضطراب مع قنوات التوزيع الاحتمالي.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-right border-collapse">
            <thead>
              <tr className="bg-slate-950 text-slate-400 border-b border-slate-800 font-mono">
                <th className="py-2.5 px-3">السنة</th>
                <th className="py-2.5 px-3 text-center">النبض المتوقع (P50)</th>
                <th className="py-2.5 px-3 text-center">نطاق النبض [P10 - P90]</th>
                <th className="py-2.5 px-3 text-center">الاضطراب الكلي (Turbulence)</th>
                <th className="py-2.5 px-3 text-center">نطاق الاضطراب [P10 - P90]</th>
                <th className="py-2.5 px-3 text-center">حصة البنية التحتية</th>
                <th className="py-2.5 px-3 text-center">حصة القرارات</th>
                <th className="py-2.5 px-3 text-center">حصة الطبيعة</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              <tr className="hover:bg-slate-800/30 bg-slate-950/40 font-bold">
                <td className="py-2.5 px-3 text-emerald-400">2024 (الأساس الفعلي)</td>
                <td className="py-2.5 px-3 text-center text-slate-200">+22.43</td>
                <td className="py-2.5 px-3 text-center text-slate-500">[22.43 - 22.43]</td>
                <td className="py-2.5 px-3 text-center text-slate-200">57.14</td>
                <td className="py-2.5 px-3 text-center text-slate-500">[57.14 - 57.14]</td>
                <td className="py-2.5 px-3 text-center text-slate-300">57.7%</td>
                <td className="py-2.5 px-3 text-center text-slate-300">41.7%</td>
                <td className="py-2.5 px-3 text-center text-slate-300">0.6%</td>
              </tr>
              {forecastData.fleetSnapshots.map((snap) => (
                <tr
                  key={snap.targetYear}
                  className={`hover:bg-slate-800/30 ${
                    snap.targetYear === selectedYear ? 'bg-cyan-950/20' : ''
                  }`}
                >
                  <td className="py-2.5 px-3 font-bold text-slate-200">{snap.targetYear}</td>
                  <td className="py-2.5 px-3 text-center text-cyan-300 font-bold">
                    {snap.expectedPulse > 0 ? `+${snap.expectedPulse}` : snap.expectedPulse}
                  </td>
                  <td className="py-2.5 px-3 text-center text-slate-400">
                    [{snap.p10Pulse} → {snap.p90Pulse}]
                  </td>
                  <td className="py-2.5 px-3 text-center text-amber-300 font-bold">{snap.expectedTurbulence}</td>
                  <td className="py-2.5 px-3 text-center text-slate-400">
                    [{snap.p10Turbulence} → {snap.p90Turbulence}]
                  </td>
                  <td className="py-2.5 px-3 text-center text-slate-300">
                    {snap.layerShares.infrastructurePercentage}%
                  </td>
                  <td className="py-2.5 px-3 text-center text-slate-300">
                    {snap.layerShares.humanSystemPercentage}%
                  </td>
                  <td className="py-2.5 px-3 text-center text-slate-300">
                    {snap.layerShares.naturePercentage}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detailed Series Projections Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div>
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Filter className="w-5 h-5 text-cyan-400" />
              <span>استشراف السلاسل الـ 50 حتى عام {selectedYear}</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              متابعة المحرك الرياضي لكل سلسلة مع تصنيف المحرك الديناميكي ومؤشر الهشاشة (Fragility Index).
            </p>
          </div>

          <div className="flex items-center gap-2">
            {[
              { id: 'all', label: 'الكل (50)' },
              { id: 'infrastructure', label: 'البنية التحتية' },
              { id: 'human_system', label: 'القرارات والأنظمة' },
              { id: 'nature', label: 'الطبيعة' }
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setSelectedLayerFilter(f.id as any)}
                className={`px-3 py-1 rounded text-xs transition-all ${
                  selectedLayerFilter === f.id
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                    : 'text-slate-400 hover:text-slate-200 bg-slate-950 border border-slate-800'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto max-h-96">
          <table className="w-full text-xs text-right border-collapse">
            <thead className="sticky top-0 bg-slate-950 text-slate-400 border-b border-slate-800 font-mono">
              <tr>
                <th className="py-2.5 px-3">السلسلة</th>
                <th className="py-2.5 px-3 text-center">الطبقة</th>
                <th className="py-2.5 px-3 text-center">أساس 2024</th>
                <th className="py-2.5 px-3 text-center">المتوقع لعام {selectedYear}</th>
                <th className="py-2.5 px-3 text-center">نطاق الثقة [P10 - P90]</th>
                <th className="py-2.5 px-3 text-center">مؤشر الهشاشة</th>
                <th className="py-2.5 px-3">المحرك الديناميكي الحاكم</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filteredSeries.map((s) => {
                const targetProj =
                  s.projections.find((p) => p.year === selectedYear) ||
                  s.projections[s.projections.length - 1];

                const delta = targetProj.expectedScore - s.baseScore2024;
                return (
                  <tr key={s.seriesId} className="hover:bg-slate-800/30">
                    <td className="py-2 px-3">
                      <div className="font-bold text-slate-200">{s.nameAr}</div>
                      <div className="text-[10px] text-slate-500">{s.seriesId}</div>
                    </td>
                    <td className="py-2 px-3 text-center">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] border ${
                          s.layer === 'infrastructure'
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : s.layer === 'human_system'
                            ? 'bg-purple-500/10 text-purple-400 border-purple-500/20'
                            : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                        }`}
                      >
                        {s.layer}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-center text-slate-300 font-bold">
                      {s.baseScore2024}
                    </td>
                    <td className="py-2 px-3 text-center">
                      <span
                        className={`font-bold ${
                          targetProj.expectedScore >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {targetProj.expectedScore}
                      </span>
                      <span className="text-[10px] text-slate-500 mr-1.5">
                        ({delta >= 0 ? `+${delta.toFixed(2)}` : delta.toFixed(2)})
                      </span>
                    </td>
                    <td className="py-2 px-3 text-center text-slate-400">
                      [{targetProj.p10Score} → {targetProj.p90Score}]
                    </td>
                    <td className="py-2 px-3 text-center">
                      <span
                        className={`font-bold ${
                          s.fragilityIndex > 0.5 ? 'text-amber-400' : 'text-slate-400'
                        }`}
                      >
                        {s.fragilityIndex}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-300 text-[11px] truncate max-w-xs">
                      {s.dominantDriver}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Historical Hindcasting Verification Section (Testing the future engine on the past) */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div>
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-amber-400" />
              <span>فحص الاستشراف على الماضي (Historical Hindcasting Verification: 1973 → 2024)</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              تطبيق خوارزمية محرك الاستشراف ذاتها بأثر رجعي على الحقب التاريخية ومقارنة مخرجاتها بالبيانات الحقيقية المسجلة.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono px-3 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
              متوسط دقة الاتجاه: {(hindcastResults.reduce((a, b) => a + b.hitRatePercent, 0) / hindcastResults.length).toFixed(1)}%
            </span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-right border-collapse">
            <thead>
              <tr className="bg-slate-950 text-slate-400 border-b border-slate-800 font-mono">
                <th className="py-2.5 px-3">الحقبة التاريخية</th>
                <th className="py-2.5 px-3 text-center">طور النظام المقاس (Regime)</th>
                <th className="py-2.5 px-3 text-center">دقة الاتجاه (Hit Rate)</th>
                <th className="py-2.5 px-3 text-center">متوسط الخطأ (MAE)</th>
                <th className="py-2.5 px-3 text-center">تغير النبض الفعلي</th>
                <th className="py-2.5 px-3 text-center">تغير النبض المستشرف</th>
                <th className="py-2.5 px-3 text-center">تطابق نبض النظام؟</th>
                <th className="py-2.5 px-3 text-center">دقة البنية التحتية</th>
                <th className="py-2.5 px-3 text-center">دقة القرارات</th>
                <th className="py-2.5 px-3 text-center">دقة الطبيعة</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {hindcastResults.map((h) => {
                const isCrisis = h.fromYear === 2008 || h.fromYear === 2020;
                return (
                  <tr
                    key={`${h.fromYear}-${h.toYear}`}
                    className={`hover:bg-slate-800/30 ${
                      h.fromYear === 2020 ? 'bg-emerald-950/20 font-bold' : isCrisis ? 'bg-amber-950/10' : ''
                    }`}
                  >
                    <td className="py-2.5 px-3 text-slate-200">
                      {h.fromYear} → {h.toYear}
                      {h.fromYear === 2020 && (
                        <span className="mr-2 text-[10px] text-emerald-400 font-normal">
                          (Holdout)
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {isCrisis ? (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-rose-500/10 text-rose-300 border border-rose-500/30 font-bold">
                          🚨 ذعر وصدمة مالية
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700">
                          ⚖️ استقرار وتراكم
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <span
                        className={`font-bold ${
                          h.hitRatePercent >= 70
                            ? 'text-emerald-400'
                            : h.hitRatePercent >= 60
                            ? 'text-cyan-400'
                            : 'text-amber-400'
                        }`}
                      >
                        {h.hitRatePercent}%
                      </span>
                      <span className="text-[10px] text-slate-500 mr-1">
                        ({h.directionalHitCount}/50)
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center text-slate-300">
                      {h.meanAbsoluteError}
                    </td>
                    <td className="py-2.5 px-3 text-center text-slate-400">
                      {h.actualNetPulseChange > 0 ? `+${h.actualNetPulseChange}` : h.actualNetPulseChange}
                    </td>
                    <td className="py-2.5 px-3 text-center text-slate-400">
                      {h.forecastNetPulseChange > 0 ? `+${h.forecastNetPulseChange}` : h.forecastNetPulseChange}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      {h.pulseDirectionMatch ? (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                          نعم (مطابق)
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] bg-rose-500/10 text-rose-400 border border-rose-500/30">
                          لا (معكوس)
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-center text-emerald-300">
                      {h.layerBreakdown.infraHitRate}%
                    </td>
                    <td className="py-2.5 px-3 text-center text-purple-300">
                      {h.layerBreakdown.humanHitRate}%
                    </td>
                    <td className="py-2.5 px-3 text-center text-cyan-300">
                      {h.layerBreakdown.natureHitRate}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-slate-950/60 p-4 rounded-lg border border-slate-800">
          <div className="space-y-1">
            <span className="text-emerald-400 font-bold">الدروس المستفادة من فحص الماضي (Empirical Findings):</span>
            <p className="text-slate-400 leading-relaxed">
              تثبت طبقة البنية التحتية أعلى نسبة نجاح استشرافي مستمر (بمتوسط يفوق 80% وتصل إلى 100% في بعض الحقب)، بسبب استقرار قانون تراكم رأس المال المادي.
            </p>
          </div>
          <div className="space-y-1">
            <span className="text-cyan-400 font-bold">التحقق الشامل لنموذج الأطوار الثنائية (Dual-Regime Validation):</span>
            <p className="text-slate-400 leading-relaxed">
              تفعيل كاشف طور الأزمات والذعر خفض الخطأ المطلق في 2008 من 0.632 إلى 0.579 وفي 2020 إلى 0.274، مع حماية واستقرار الدقة بنسبة 100% في فترات الاستقرار الهادئة (1973، 1980، 1990، 2013).
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
