import React, { useState, useMemo } from 'react';
import {
  Compass,
  ArrowRight,
  TrendingUp,
  Activity,
  Layers,
  Network,
  Share2,
  AlertTriangle,
  Zap,
  Clock,
  Filter,
  Info,
  FileCheck,
  CheckCircle,
  XCircle,
  HelpCircle
} from 'lucide-react';
import {
  runPatternDiscoveryEngine,
  PatternDiscoveryResult,
  DiscoveredVariableProfile,
  DiscoveredLeadLagPair,
  DiscoveredRegimeCluster
} from '../utils/patternDiscoveryEngine';
import {
  generatePatternEvidenceReport,
  PatternEvidenceReport,
  EmpiricalPatternEvidence
} from '../utils/patternEvidenceReport';

export const PatternDiscoveryEngineView: React.FC = () => {
  const [selectedTab, setSelectedTab] = useState<'evidence_report' | 'lead_lag' | 'profiles' | 'regimes' | 'matrix'>('evidence_report');
  const [filterLayer, setFilterLayer] = useState<'all' | 'nature' | 'infrastructure' | 'human_system'>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [evidenceFilter, setEvidenceFilter] = useState<'all' | 'Validated' | 'Exploratory' | 'Rejected'>('all');

  const discoveryData: PatternDiscoveryResult = useMemo(() => {
    return runPatternDiscoveryEngine();
  }, []);

  const evidenceReport: PatternEvidenceReport = useMemo(() => {
    return generatePatternEvidenceReport();
  }, []);

  const filteredEvidencePatterns = useMemo(() => {
    return evidenceReport.patterns.filter(p => {
      if (evidenceFilter === 'all') return true;
      return p.classification === evidenceFilter;
    });
  }, [evidenceReport, evidenceFilter]);

  const filteredProfiles = useMemo(() => {
    return discoveryData.discoveredProfiles.filter((p) => {
      const matchesLayer = filterLayer === 'all' || p.layer === filterLayer;
      const matchesSearch =
        searchTerm === '' ||
        p.nameAr.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.nameEn.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.id.toLowerCase().includes(searchTerm.toLowerCase());
      return matchesLayer && matchesSearch;
    });
  }, [discoveryData, filterLayer, searchTerm]);

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded text-xs font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                Pattern Discovery Engine
              </span>
              <span className="text-xs text-slate-400 font-mono">1973 → 2024 Historical Grounding</span>
            </div>
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <Compass className="w-6 h-6 text-cyan-400" />
              <span>محرك اكتشاف الأنماط والمتغيرات القائدة والتراخي الزمني</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1 max-w-3xl leading-relaxed">
              استخراج العلاقات الحاكمة بين السلاسل الخمسين آلياً من مساراتها التاريخية الفعلية (Lagged Cross-Correlation & Lead Indices)، لتحديد أي المتغيرات يقود النظام عالمياً (Leading Drivers) وأيها يمتص الصدمات متأخراً (Lagging Absorbers) دون افتراضات مسبقة.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-center min-w-[110px]">
              <span className="block text-[10px] text-slate-500">أزواج تم تقييمها</span>
              <span className="text-sm font-bold font-mono text-cyan-400">
                {discoveryData.discoverySummary.totalHistoricalPairsEvaluated} زوجاً
              </span>
            </div>
            <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-center min-w-[110px]">
              <span className="block text-[10px] text-slate-500">المتغير الأكثر قيادة</span>
              <span className="text-xs font-bold font-mono text-emerald-400 truncate block max-w-[130px]">
                {discoveryData.discoverySummary.highestLeadingSeries.nameAr}
              </span>
            </div>
            <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-center min-w-[110px]">
              <span className="block text-[10px] text-slate-500">أكبر ممتص متأخر</span>
              <span className="text-xs font-bold font-mono text-purple-400 truncate block max-w-[130px]">
                {discoveryData.discoverySummary.mostLaggingAbsorber.nameAr}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs Control */}
      <div className="flex border-b border-slate-800 gap-2 pb-2 overflow-x-auto">
        <button
          onClick={() => setSelectedTab('evidence_report')}
          className={`px-4 py-2 rounded-lg text-xs font-medium transition-colors flex items-center gap-2 whitespace-nowrap ${
            selectedTab === 'evidence_report'
              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30 font-bold'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <FileCheck className="w-4 h-4 text-amber-400" />
          <span>تقرير أدلة الأنماط الصامدة (Pattern Evidence Report)</span>
          <span className="px-1.5 py-0.2 bg-amber-500/20 text-amber-300 rounded-full text-[10px]">
            {evidenceReport.validatedPatternsCount} Validated
          </span>
        </button>
        <button
          onClick={() => setSelectedTab('lead_lag')}
          className={`px-4 py-2 rounded-lg text-xs font-medium transition-colors flex items-center gap-2 whitespace-nowrap ${
            selectedTab === 'lead_lag'
              ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Network className="w-4 h-4" />
          <span>شبكة القيادة والتراخي (Lead-Lag Network)</span>
        </button>
        <button
          onClick={() => setSelectedTab('profiles')}
          className={`px-4 py-2 rounded-lg text-xs font-medium transition-colors flex items-center gap-2 ${
            selectedTab === 'profiles'
              ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>تصنيف الأدوار للـ 50 متغيراً (Variable Roles)</span>
        </button>
        <button
          onClick={() => setSelectedTab('regimes')}
          className={`px-4 py-2 rounded-lg text-xs font-medium transition-colors flex items-center gap-2 ${
            selectedTab === 'regimes'
              ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>أطوار النظام التاريخية المكتشفة (Regime Clusters)</span>
        </button>
        <button
          onClick={() => setSelectedTab('matrix')}
          className={`px-4 py-2 rounded-lg text-xs font-medium transition-colors flex items-center gap-2 ${
            selectedTab === 'matrix'
              ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>مصفوفة تسارع الانتقالات التاريخية</span>
        </button>
      </div>

      {/* Tab 0: Pattern Evidence Report */}
      {selectedTab === 'evidence_report' && (
        <div className="space-y-6">
          {/* Executive Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
              <div>
                <span className="text-[11px] text-slate-400 block">إجمالي الأنماط المرشحة</span>
                <span className="text-xl font-bold font-mono text-slate-100">{evidenceReport.totalCandidatesEvaluated}</span>
              </div>
              <Compass className="w-8 h-8 text-slate-600" />
            </div>

            <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-xl p-4 flex items-center justify-between">
              <div>
                <span className="text-[11px] text-emerald-400 block font-semibold">صامدة ومثبتة (Validated)</span>
                <span className="text-xl font-bold font-mono text-emerald-300">{evidenceReport.validatedPatternsCount}</span>
                <span className="text-[10px] text-emerald-500 block">صمدت خارج العينة</span>
              </div>
              <CheckCircle className="w-8 h-8 text-emerald-400/80" />
            </div>

            <div className="bg-amber-950/20 border border-amber-500/30 rounded-xl p-4 flex items-center justify-between">
              <div>
                <span className="text-[11px] text-amber-400 block font-semibold">استكشافية (Exploratory)</span>
                <span className="text-xl font-bold font-mono text-amber-300">{evidenceReport.exploratoryPatternsCount}</span>
                <span className="text-[10px] text-amber-500 block">تحتاج دقة مكانية</span>
              </div>
              <HelpCircle className="w-8 h-8 text-amber-400/80" />
            </div>

            <div className="bg-rose-950/20 border border-rose-500/30 rounded-xl p-4 flex items-center justify-between">
              <div>
                <span className="text-[11px] text-rose-400 block font-semibold">مرفوضة تماماً (Rejected)</span>
                <span className="text-xl font-bold font-mono text-rose-300">{evidenceReport.rejectedPatternsCount}</span>
                <span className="text-[10px] text-rose-500 block">ارتباطات كاذبة</span>
              </div>
              <XCircle className="w-8 h-8 text-rose-400/80" />
            </div>
          </div>

          {/* Scientific Guidance Callout */}
          <div className="bg-slate-900/90 border border-amber-500/30 rounded-xl p-4 flex items-start gap-3 text-xs leading-relaxed">
            <Info className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-bold text-slate-200 block">
                ميثاق النزاهة العلمية لحصاد الأدلة (Empirical Evidence Charter):
              </span>
              <p className="text-slate-400">
                لا تتحول أي علاقة إلى قاعدة رياضية أو كود استشراف إلا إذا نالت تصنيف <span className="text-emerald-400 font-bold">Validated</span> (أي تكررت في 4 انتقالات تاريخية على الأقل وأثبتت صحتها خارج العينة في انتقال 2020→2024). الأنماط المصنفة <span className="text-rose-400 font-bold">Rejected</span> تم حظرها صراحة لأنها علاقات سطحية أو مصادفات إحصائية.
              </p>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 font-mono">تصفية حسب التصنيف:</span>
              <div className="flex gap-1">
                {(['all', 'Validated', 'Exploratory', 'Rejected'] as const).map(cat => (
                  <button
                    key={cat}
                    onClick={() => setEvidenceFilter(cat)}
                    className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                      evidenceFilter === cat
                        ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                        : 'bg-slate-900 text-slate-400 hover:bg-slate-800 border border-slate-800'
                    }`}
                  >
                    {cat === 'all' ? 'الكل (7)' : cat}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Pattern Cards List */}
          <div className="space-y-4">
            {filteredEvidencePatterns.map(pat => (
              <div
                key={pat.id}
                className={`bg-slate-900/90 border rounded-xl p-5 shadow-lg space-y-4 transition-all ${
                  pat.classification === 'Validated'
                    ? 'border-emerald-500/40 hover:border-emerald-500/70'
                    : pat.classification === 'Exploratory'
                    ? 'border-amber-500/40 hover:border-amber-500/70'
                    : 'border-rose-500/40 opacity-75 hover:opacity-100'
                }`}
              >
                {/* Card Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2.5 py-0.5 rounded text-xs font-bold font-mono ${
                          pat.classification === 'Validated'
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                            : pat.classification === 'Exploratory'
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                        }`}
                      >
                        {pat.classification}
                      </span>
                      <h4 className="text-sm font-bold text-slate-100">{pat.patternTitleAr}</h4>
                    </div>
                    <span className="text-[11px] font-mono text-slate-500 block mt-0.5">{pat.patternTitleEn}</span>
                  </div>

                  <div className="flex items-center gap-2 text-xs font-mono">
                    <span className="bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-slate-300">
                      قوة الارتباط: <strong className="text-cyan-400">r={pat.couplingStrengthR}</strong>
                    </span>
                    <span className="bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-slate-300">
                      التراخي (Lag): <strong className="text-amber-400">{pat.lagSteps} خطوة</strong>
                    </span>
                    <span className="bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-slate-300">
                      تكرار الظهور: <strong className="text-emerald-400">{pat.occurrenceCount} انتقالات</strong>
                    </span>
                  </div>
                </div>

                {/* Variables Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  {/* Primary */}
                  <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 space-y-2">
                    <span className="text-[11px] font-bold text-cyan-400 flex items-center gap-1">
                      <Activity className="w-3.5 h-3.5" />
                      <span>المتغيرات الأساسية القائدة (Primary Drivers):</span>
                    </span>
                    <ul className="space-y-1.5 font-mono">
                      {pat.primaryVariables.map(v => (
                        <li key={v.id} className="flex items-center justify-between text-slate-300 bg-slate-900/80 px-2 py-1 rounded">
                          <span>{v.nameAr}</span>
                          <span className="text-[10px] text-slate-500">{v.layer}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Secondary */}
                  <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 space-y-2">
                    <span className="text-[11px] font-bold text-purple-400 flex items-center gap-1">
                      <Layers className="w-3.5 h-3.5" />
                      <span>المتغيرات الثانوية التابعة (Secondary Absorbers):</span>
                    </span>
                    <ul className="space-y-1.5 font-mono">
                      {pat.secondaryVariables.map(v => (
                        <li key={v.id} className="flex items-center justify-between text-slate-300 bg-slate-900/80 px-2 py-1 rounded">
                          <span>{v.nameAr}</span>
                          <span className="text-[10px] text-slate-500">{v.layer}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {/* Transition & Regime Context */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
                  <div className="bg-slate-950/40 p-2.5 rounded border border-slate-800">
                    <span className="text-[10px] text-slate-500 block">الانتقالات النشطة:</span>
                    <span className="text-slate-300">{pat.activeTransitions.join(', ')}</span>
                  </div>
                  <div className="bg-slate-950/40 p-2.5 rounded border border-slate-800">
                    <span className="text-[10px] text-slate-500 block">الأطوار المرتبطة (Regimes):</span>
                    <span className="text-slate-300 truncate block">{pat.associatedRegimes.join('، ')}</span>
                  </div>
                  <div className="bg-slate-950/40 p-2.5 rounded border border-slate-800">
                    <span className="text-[10px] text-slate-500 block">اختبار خارج العينة (2020→2024):</span>
                    <span
                      className={`font-bold ${
                        pat.outOfSampleStatus.holdoutPerformance === 'confirmed'
                          ? 'text-emerald-400'
                          : pat.outOfSampleStatus.holdoutPerformance === 'diverged'
                          ? 'text-rose-400'
                          : 'text-amber-400'
                      }`}
                    >
                      {pat.outOfSampleStatus.holdoutPerformance === 'confirmed'
                        ? '✓ صمد خارج العينة (Confirmed)'
                        : pat.outOfSampleStatus.holdoutPerformance === 'diverged'
                        ? '✗ تباعد وفشل (Diverged)'
                        : '؟ غير حاسم (Inconclusive)'}
                    </span>
                  </div>
                </div>

                {/* Failure Cases & Justification */}
                <div className="space-y-2 pt-2 border-t border-slate-800/80 text-xs">
                  {pat.failureCases.length > 0 && (
                    <div className="bg-slate-950/80 rounded p-2.5 border border-slate-800/80 space-y-1">
                      <span className="text-amber-400 font-bold block text-[11px]">حالات الفشل التاريخية المشاهدة:</span>
                      {pat.failureCases.map((fc, i) => (
                        <p key={i} className="text-slate-400">
                          <strong className="text-slate-300 font-mono">[{fc.transition}]:</strong> {fc.descriptionAr}
                        </p>
                      ))}
                    </div>
                  )}

                  <div className="bg-slate-950/80 rounded p-2.5 border border-slate-800/80 space-y-1">
                    <span className="text-cyan-400 font-bold block text-[11px]">التقييم العلمي النهائي للأدلة:</span>
                    <p className="text-slate-300 leading-relaxed">{pat.scientificEvidenceJustificationAr}</p>
                    <p className="text-[11px] text-slate-500 font-mono mt-1">
                      تفاصيل العينة: {pat.outOfSampleStatus.holdoutMetricNotes}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 1: Lead-Lag Network */}
      {selectedTab === 'lead_lag' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
            <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                  <Share2 className="w-4 h-4 text-cyan-400" />
                  <span>أقوى علاقات السبق الزمني المكتشفة إحصائياً (Top Discovered Lead-Lag Interactions)</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  المتغير القائد (Leading) يتحرك في الحقبة (t) ليتلوه المتغير التابع (Lagging) في الحقبة التالية (t+1) بمعامل ارتباط مرتفع.
                </p>
              </div>
              <span className="text-xs font-mono text-slate-500">معامل الارتباط r ≥ 0.75</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-right border-collapse">
                <thead>
                  <tr className="bg-slate-950 text-slate-400 border-b border-slate-800 font-mono">
                    <th className="py-2.5 px-3">المتغير القائد (Leading Driver)</th>
                    <th className="py-2.5 px-3 text-center">طبقة القائد</th>
                    <th className="py-2.5 px-3 text-center">اتجاه التأثير</th>
                    <th className="py-2.5 px-3">المتغير التابع (Lagging Impact)</th>
                    <th className="py-2.5 px-3 text-center">طبقة التابع</th>
                    <th className="py-2.5 px-3 text-center">قوة الترابط (Coupling)</th>
                    <th className="py-2.5 px-3 text-center">فترة التراخي الزمني</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {discoveryData.topLeadLagInteractions.map((pair, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 font-semibold text-slate-200">
                        {pair.leadingSeriesNameAr}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] ${
                            pair.leadingLayer === 'nature'
                              ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                              : pair.leadingLayer === 'infrastructure'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                              : 'bg-purple-500/10 text-purple-400 border border-purple-500/30'
                          }`}
                        >
                          {pair.leadingLayer === 'nature'
                            ? 'طبيعة'
                            : pair.leadingLayer === 'infrastructure'
                            ? 'بنية تحتية'
                            : 'قرارات بشرية'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <ArrowRight className="w-4 h-4 mx-auto text-amber-400 inline" />
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-slate-300">
                        {pair.laggingSeriesNameAr}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] ${
                            pair.laggingLayer === 'nature'
                              ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                              : pair.laggingLayer === 'infrastructure'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                              : 'bg-purple-500/10 text-purple-400 border border-purple-500/30'
                          }`}
                        >
                          {pair.laggingLayer === 'nature'
                            ? 'طبيعة'
                            : pair.laggingLayer === 'infrastructure'
                            ? 'بنية تحتية'
                            : 'قرارات بشرية'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span className="font-bold text-emerald-400">
                          {(pair.couplingStrength * 100).toFixed(0)}%
                        </span>
                        <span className="text-[10px] text-slate-500 mr-1">(r={pair.correlation})</span>
                      </td>
                      <td className="py-2.5 px-3 text-center text-slate-400">
                        حقبة واحدة (~ 5-7 سنوات)
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Core Findings callout */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
              <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                <Zap className="w-4 h-4" />
                <span>الظاهرة الأولى: قاطرة الغذاء والطاقة تقود النظام البشري</span>
              </span>
              <p className="text-xs text-slate-400 leading-relaxed">
                تُظهر مصفوفة التراخي أن التغيرات في <span className="text-slate-200">مخزون الحبوب (s15)</span> و<span className="text-slate-200">الأسمدة النيتروجينية (s17)</span> و<span className="text-slate-200">النفط الخام (s18)</span> تسبق زمنياً التغير في معدلات التضخم والبطالة والنمو الاقتصادي بحقبة كاملة، مما يجعل أمن الإمداد المادي هو القائد الحقيقي للقرارات المالية اللاحقة.
              </p>
            </div>

            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
              <span className="text-xs font-bold text-amber-400 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" />
                <span>الظاهرة الثانية: معدلات البطالة والإفلاس هي الممتص النهائي</span>
              </span>
              <p className="text-xs text-slate-400 leading-relaxed">
                أظهر الفحص أن <span className="text-slate-200">معدلات البطالة (s37)</span> و<span className="text-slate-200">إفلاس المؤسسات (s39)</span> تأتي في أسفل قائمة التراخي الزمني (Lagging Absorbers) بمؤشر قيادة سالب (-0.58)، أي أنها لا تقود الأزمات بل تستقبل آثار الصدمات المتراكمة من الطبقات الأخرى.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Discovered Variable Profiles */}
      {selectedTab === 'profiles' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-200">
                  تصنيف دور كل متغير في المنظومة (Variable Operational Roles)
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  حساب مؤشر القيادة (Lead Index) ومركزية التشابك لكل سلسلة من واقع سلوكها عبر التاريخ.
                </p>
              </div>

              {/* Filters */}
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <input
                  type="text"
                  placeholder="بحث في السلاسل..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 focus:outline-none focus:border-cyan-500"
                />
                <select
                  value={filterLayer}
                  onChange={(e) => setFilterLayer(e.target.value as any)}
                  className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="all">كل الطبقات (50)</option>
                  <option value="nature">الطبيعة (10)</option>
                  <option value="infrastructure">البنية التحتية (20)</option>
                  <option value="human_system">النظام البشري (20)</option>
                </select>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-right border-collapse">
                <thead>
                  <tr className="bg-slate-950 text-slate-400 border-b border-slate-800 font-mono">
                    <th className="py-2.5 px-3">السلسلة</th>
                    <th className="py-2.5 px-3 text-center">الطبقة</th>
                    <th className="py-2.5 px-3 text-center">الدور المكتشف</th>
                    <th className="py-2.5 px-3 text-center">مؤشر القيادة (Lead Index)</th>
                    <th className="py-2.5 px-3 text-center">المركزية (Centrality)</th>
                    <th className="py-2.5 px-3 text-center">معدل التذبذب</th>
                    <th className="py-2.5 px-3">أبرز السلاسل التابعة زمنياً</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {filteredProfiles.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-800/40">
                      <td className="py-2 px-3 font-semibold text-slate-200">
                        {p.nameAr}
                        <span className="text-[10px] text-slate-500 block font-normal">{p.id}</span>
                      </td>
                      <td className="py-2 px-3 text-center">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] ${
                            p.layer === 'nature'
                              ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                              : p.layer === 'infrastructure'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                              : 'bg-purple-500/10 text-purple-400 border border-purple-500/30'
                          }`}
                        >
                          {p.layer === 'nature'
                            ? 'طبيعة'
                            : p.layer === 'infrastructure'
                            ? 'بنية تحتية'
                            : 'قرارات'}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-center">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            p.role === 'primary_driver'
                              ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30'
                              : p.role === 'secondary_absorber'
                              ? 'bg-purple-500/10 text-purple-300 border border-purple-500/30'
                              : 'bg-slate-800 text-slate-300'
                          }`}
                        >
                          {p.role === 'primary_driver'
                            ? 'قاطرة قائدة (Primary)'
                            : p.role === 'secondary_absorber'
                            ? 'ممتص متأخر (Absorber)'
                            : 'ناقل وسيط (Transmitter)'}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-center">
                        <span
                          className={`font-bold ${
                            p.leadIndex > 0.2
                              ? 'text-emerald-400'
                              : p.leadIndex < -0.2
                              ? 'text-rose-400'
                              : 'text-slate-400'
                          }`}
                        >
                          {p.leadIndex > 0 ? `+${p.leadIndex}` : p.leadIndex}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-center text-slate-300">
                        {p.hubCentrality}
                      </td>
                      <td className="py-2 px-3 text-center text-slate-400">
                        {p.volatilityRate}
                      </td>
                      <td className="py-2 px-3 text-[11px] text-slate-400 max-w-xs truncate">
                        {p.topInfluencedSeries.length > 0
                          ? p.topInfluencedSeries.map((s) => s.nameAr).join('، ')
                          : 'لا توجد توابع قوية'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Discovered Regime Clusters */}
      {selectedTab === 'regimes' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-200">
                أطوار النظام التاريخية المكتشفة من بيانات 1973 - 2024
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                تجمع الحقب التاريخية في كتل هيكلية تشترك في مستويات النبض البشري ومستوى تماسك المنظومة واستقرارها.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {discoveryData.regimeClusters.map((cluster) => (
                <div
                  key={cluster.id}
                  className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3 relative overflow-hidden"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-slate-200">{cluster.nameAr}</span>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-900 text-cyan-400 border border-slate-800">
                      [{cluster.benchmarkYears.join(', ')}]
                    </span>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed">{cluster.descriptionAr}</p>

                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-900 text-xs font-mono">
                    <div className="bg-slate-900/60 p-2 rounded text-center">
                      <span className="text-[10px] text-slate-500 block">صافي النبض</span>
                      <span
                        className={`font-bold ${
                          cluster.meanSystemPulse >= 0 ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {cluster.meanSystemPulse >= 0
                          ? `+${cluster.meanSystemPulse}`
                          : cluster.meanSystemPulse}
                      </span>
                    </div>
                    <div className="bg-slate-900/60 p-2 rounded text-center">
                      <span className="text-[10px] text-slate-500 block">الاستقرار</span>
                      <span className="font-bold text-amber-400">
                        {(cluster.stabilityIndex * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="bg-slate-900/60 p-2 rounded text-center">
                      <span className="text-[10px] text-slate-500 block">التماسك (Coherence)</span>
                      <span className="font-bold text-cyan-400">
                        {(cluster.systemCoherence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Empirical Transition Matrix */}
      {selectedTab === 'matrix' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
            <div className="border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-200">
                مصفوفة تسارع المتغيرات في الانتقالات التاريخية الـ 6
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                تحديد السلاسل الثلاث التي قادت أكبر تسارع في كل انتقال تاريخي، مع قياس مدى التوافق بين البنية والقرارات.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-right border-collapse">
                <thead>
                  <tr className="bg-slate-950 text-slate-400 border-b border-slate-800 font-mono">
                    <th className="py-2.5 px-3">الانتقال التاريخي</th>
                    <th className="py-2.5 px-3">المتغيرات الثلاثة الأكثر تسارعاً (Top Velocities)</th>
                    <th className="py-2.5 px-3 text-center">تماسك الانتقال (Coherence)</th>
                    <th className="py-2.5 px-3">التوصيف الهيكلي للانتقال</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {discoveryData.empiricalTransitionMatrix.map((m, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 font-bold text-slate-200">
                        {m.fromYear} → {m.toYear}
                      </td>
                      <td className="py-2.5 px-3 text-cyan-300">
                        {m.systemLeadVector.join(' ⟵ ')}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span
                          className={`font-bold ${
                            m.coherenceScore > 0.6 ? 'text-emerald-400' : 'text-amber-400'
                          }`}
                        >
                          {(m.coherenceScore * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                        {m.fromYear === 2001
                          ? 'انفجار الصدمة المالية وتفكك التوافق الرأسمالي'
                          : m.fromYear === 1980
                          ? 'توسع صناعي هادئ بقيادة الطاقة والمواد'
                          : m.fromYear === 2020
                          ? 'صدمة مزدوجة للجائحة وإعادة هيكلة الطاقة'
                          : 'تحول تراكمي تدريجي'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
