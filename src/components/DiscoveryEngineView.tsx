import React, { useState, useMemo } from 'react';
import {
  Sparkles,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ExternalLink,
  Upload,
  Layers,
  Database,
  Sliders,
  Activity,
  ArrowRight,
  TrendingDown,
  Info
} from 'lucide-react';
import { StandardTimeSeries, DiscoveryExecutionResult } from '../types';
import { REAL_TIME_SERIES_LIBRARY } from '../data/timeSeriesLibrary';
import { runNeutralDiscoveryPipeline } from '../utils/discoveryEngineCore';

export const DiscoveryEngineView: React.FC = () => {
  const [selectedSeriesId, setSelectedSeriesId] = useState<string>('wb-global-inflation');
  const [windowSize, setWindowSize] = useState<number>(8);
  const [surrogateCount, setSurrogateCount] = useState<number>(150);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [activeSubTab, setActiveSubTab] = useState<'motifs' | 'surrogate' | 'intervals' | 'raw_data'>('motifs');

  // Custom data input state
  const [customSeries, setCustomSeries] = useState<StandardTimeSeries | null>(null);
  const [customInputText, setCustomInputText] = useState<string>('');
  const [showCustomModal, setShowCustomModal] = useState<boolean>(false);

  // Active series resolution
  const activeSeries = useMemo(() => {
    if (customSeries && selectedSeriesId === customSeries.id) {
      return customSeries;
    }
    return REAL_TIME_SERIES_LIBRARY.find((s) => s.id === selectedSeriesId) || REAL_TIME_SERIES_LIBRARY[0];
  }, [selectedSeriesId, customSeries]);

  // Live execution result state
  const [result, setResult] = useState<DiscoveryExecutionResult | null>(() => {
    return runNeutralDiscoveryPipeline(REAL_TIME_SERIES_LIBRARY[0], 8, 100);
  });

  // Handle run discovery
  const handleExecuteDiscovery = () => {
    setIsRunning(true);
    // Use setTimeout so the UI can update spinner state before synchronous Monte Carlo permutations
    setTimeout(() => {
      const res = runNeutralDiscoveryPipeline(activeSeries, windowSize, surrogateCount);
      setResult(res);
      setIsRunning(false);
    }, 50);
  };

  // Parse custom CSV / TSV input
  const handleParseCustomData = () => {
    try {
      const lines = customInputText.trim().split('\n');
      const points: StandardTimeSeries['points'] = [];

      lines.forEach((line, index) => {
        const parts = line.split(/[,\t;]/).map((p) => p.trim());
        if (parts.length >= 2) {
          const dateStr = parts[0];
          const val = parseFloat(parts[1]);
          if (!isNaN(val)) {
            const timestamp = Date.parse(dateStr) || index * 86400000;
            points.push({
              date: dateStr,
              timestamp,
              value: val
            });
          }
        }
      });

      if (points.length < 16) {
        alert('يرجى إدخال ما لا يقل عن 16 نقطة بيانات صالحة لإجراء كشف الأنماط.');
        return;
      }

      const newSeries: StandardTimeSeries = {
        id: `custom-series-${Date.now()}`,
        name: 'سلسلة بيانات مخصصة (User Input Series)',
        source: 'مدخلات المستخدم المباشرة (Direct Input / CSV)',
        indicatorCode: 'CUSTOM_USER_DATA',
        frequency: 'annual',
        unit: 'وحدات مخصصة',
        description: `سلسلة مخصصة تم إدخالها يدوياً وتتضمن ${points.length} نقطة زمنية.`,
        points
      };

      setCustomSeries(newSeries);
      setSelectedSeriesId(newSeries.id);
      setShowCustomModal(false);

      // Execute on custom series
      const res = runNeutralDiscoveryPipeline(newSeries, windowSize, surrogateCount);
      setResult(res);
    } catch {
      alert('حدث خطأ في معالجة البيانات المدخلة. تأكد من صيغة: التاريخ, القيمة في كل سطر.');
    }
  };

  const currentMotif = result?.motifs[0];

  // Helper to render simple SVG sparkline for the main series
  const renderTimelineSvg = () => {
    if (!activeSeries || activeSeries.points.length === 0) return null;
    const values = activeSeries.points.map((p) => p.value);
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal || 1;

    const width = 800;
    const height = 160;
    const padding = 20;

    const pointsSvg = activeSeries.points
      .map((p, idx) => {
        const x = padding + (idx / (values.length - 1)) * (width - 2 * padding);
        const y = height - padding - ((p.value - minVal) / range) * (height - 2 * padding);
        return `${x},${y}`;
      })
      .join(' ');

    // Highlight segments A and B if motif exists
    const renderOccurrenceHighlight = (startIndex: number, color: string, label: string) => {
      if (!currentMotif || startIndex < 0) return null;
      const x1 = padding + (startIndex / (values.length - 1)) * (width - 2 * padding);
      const x2 = padding + ((startIndex + currentMotif.windowSize - 1) / (values.length - 1)) * (width - 2 * padding);
      return (
        <g key={`${label}-${startIndex}`}>
          <rect
            x={x1 - 2}
            y={padding - 5}
            width={Math.max(x2 - x1 + 4, 6)}
            height={height - 2 * padding + 10}
            fill={color}
            fillOpacity="0.25"
            stroke={color}
            strokeWidth="1.5"
            rx="4"
          />
          <text
            x={x1}
            y={padding - 8}
            fill={color}
            fontSize="10"
            fontFamily="monospace"
            fontWeight="bold"
          >
            {label}
          </text>
        </g>
      );
    };

    return (
      <div className="w-full overflow-x-auto bg-slate-950/80 p-4 rounded-xl border border-slate-800">
        <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-mono">
          <span>{activeSeries.points[0].date} ({values[0]})</span>
          <span className="text-cyan-400 font-bold">
            السلسلة الكاملة: {values.length} نقطة زمنية [{activeSeries.unit}]
          </span>
          <span>{activeSeries.points[values.length - 1].date} ({values[values.length - 1]})</span>
        </div>
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-40">
          {/* Background grid */}
          <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2} stroke="#334155" strokeDasharray="3 3" strokeWidth="0.5" />
          <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#1e293b" strokeWidth="1" />

          {/* Highlights */}
          {currentMotif && renderOccurrenceHighlight(currentMotif.occurrenceA.startIndex, '#38bdf8', 'الظهور الأول A')}
          {currentMotif && renderOccurrenceHighlight(currentMotif.occurrenceB.startIndex, '#f59e0b', 'الظهور الثاني B')}

          {/* Other occurrences if any */}
          {currentMotif?.allOccurrences?.map((occ, oIdx) => {
            if (occ.index !== currentMotif.occurrenceA.startIndex && occ.index !== currentMotif.occurrenceB.startIndex) {
              return renderOccurrenceHighlight(occ.index, '#a855f7', `تكرار #${oIdx + 1}`);
            }
            return null;
          })}

          {/* Main curve */}
          <polyline
            fill="none"
            stroke="#94a3b8"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={pointsSvg}
          />
        </svg>
      </div>
    );
  };

  // Helper to render the Overlay Shape Comparison of Motif A vs Motif B
  const renderMotifOverlaySvg = () => {
    if (!currentMotif) return null;
    const normA = currentMotif.occurrenceA.normalizedValues;
    const normB = currentMotif.occurrenceB.normalizedValues;

    const allNorm = [...normA, ...normB];
    const minVal = Math.min(...allNorm);
    const maxVal = Math.max(...allNorm);
    const range = maxVal - minVal || 1;

    const width = 500;
    const height = 200;
    const padding = 25;

    const pointsA = normA
      .map((val, idx) => {
        const x = padding + (idx / (normA.length - 1)) * (width - 2 * padding);
        const y = height - padding - ((val - minVal) / range) * (height - 2 * padding);
        return `${x},${y}`;
      })
      .join(' ');

    const pointsB = normB
      .map((val, idx) => {
        const x = padding + (idx / (normB.length - 1)) * (width - 2 * padding);
        const y = height - padding - ((val - minVal) / range) * (height - 2 * padding);
        return `${x},${y}`;
      })
      .join(' ');

    return (
      <div className="bg-slate-950/90 p-4 rounded-xl border border-slate-800">
        <div className="flex items-center justify-between text-xs mb-2">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-1.5">
              <span className="w-3 h-3 rounded-full bg-cyan-400"></span>
              <span className="text-cyan-300 font-mono text-[11px]">
                المقطع A ({currentMotif.occurrenceA.startDate} → {currentMotif.occurrenceA.endDate})
              </span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="w-3 h-3 rounded-full bg-amber-400"></span>
              <span className="text-amber-300 font-mono text-[11px]">
                المقطع B ({currentMotif.occurrenceB.startDate} → {currentMotif.occurrenceB.endDate})
              </span>
            </div>
          </div>
          <span className="text-slate-400 font-mono text-[11px]">
            المسافة الإقليدية المقيسة: <strong className="text-white">{currentMotif.distance}</strong> (تطابق {currentMotif.similarityPercentage}%)
          </span>
        </div>

        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-44">
          <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2} stroke="#334155" strokeDasharray="3 3" strokeWidth="0.5" />
          
          {/* Curve A */}
          <polyline
            fill="none"
            stroke="#38bdf8"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={pointsA}
          />
          {/* Curve B */}
          <polyline
            fill="none"
            stroke="#f59e0b"
            strokeWidth="2.5"
            strokeDasharray="4 2"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={pointsB}
          />
        </svg>
      </div>
    );
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="p-6 rounded-2xl border border-cyan-500/20 bg-gradient-to-br from-slate-900 via-slate-900/90 to-slate-950 space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 font-mono text-xs font-bold border border-cyan-500/30">
                Phase 1: Neutral Motif Discovery
              </span>
              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-xs">
                Zero A-Priori Model
              </span>
            </div>
            <h1 className="text-xl font-bold text-white mt-1">
              مختبر استكشاف البنية الزمنية المحايد (Discovery Engine)
            </h1>
            <p className="text-xs text-slate-300 max-w-3xl leading-relaxed mt-1">
              نظام استقرائي لا يفترض مسبقاً أي معادلة أو نسبة أو حدث (لا زلازل، لا أزمات، لا λ=0.618).
              يستقبل السلسلة الزمنية كأرقام مجردة، ويستخدم تقنية Matrix Profile للبحث عن المقاطع المتكررة تلقائياً،
              ثم يُخضع كل نمط لاختبار الفرضية الصفرية (Surrogate Null Model) لتأكيد ما إذا كانت البنية حقيقية أم مجرد صدفة عشوائية.
            </p>
          </div>

          <button
            onClick={() => setShowCustomModal(true)}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors flex items-center space-x-2 cursor-pointer self-start md:self-center whitespace-nowrap"
          >
            <Upload className="w-4 h-4 text-cyan-400" />
            <span>إدخال سلسلة زمنية مخصصة (CSV)</span>
          </button>
        </div>
      </div>

      {/* Control Bar: Series Selection & Parameters */}
      <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        {/* Series dropdown */}
        <div className="space-y-1.5 md:col-span-2">
          <label className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5">
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            <span>السلسلة الزمنية المعتمدة للبحث:</span>
          </label>
          <select
            value={selectedSeriesId}
            onChange={(e) => setSelectedSeriesId(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
          >
            {REAL_TIME_SERIES_LIBRARY.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.source})
              </option>
            ))}
            {customSeries && (
              <option value={customSeries.id}>
                ★ {customSeries.name} ({customSeries.points.length} نقاط)
              </option>
            )}
          </select>
          <div className="flex items-center space-x-2 text-[11px] text-slate-400">
            <span>المصدر: {activeSeries.source}</span>
            {activeSeries.provenanceUrl && (
              <a
                href={activeSeries.provenanceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-cyan-400 hover:underline flex items-center space-x-0.5"
              >
                <span>رابط التوثيق</span>
                <ExternalLink className="w-2.5 h-2.5 ml-0.5" />
              </a>
            )}
          </div>
        </div>

        {/* Window size slider */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
            <span className="flex items-center space-x-1">
              <Sliders className="w-3.5 h-3.5 text-amber-400" />
              <span>طول النافذة المنزلقة (w):</span>
            </span>
            <span className="font-mono text-cyan-400 font-bold">{windowSize} نقاط</span>
          </label>
          <input
            type="range"
            min="4"
            max="16"
            step="1"
            value={windowSize}
            onChange={(e) => setWindowSize(parseInt(e.target.value))}
            className="w-full accent-cyan-500 cursor-pointer"
          />
          <span className="text-[10px] text-slate-500 block">
            طول المقطع الفرعي المراد مقارنة شكله مع باقي السلسلة
          </span>
        </div>

        {/* Action Button */}
        <div>
          <button
            onClick={handleExecuteDiscovery}
            disabled={isRunning}
            className="w-full py-2.5 px-4 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs transition-all flex items-center justify-center space-x-2 shadow-lg shadow-cyan-500/10 cursor-pointer disabled:opacity-50"
          >
            {isRunning ? (
              <>
                <RotateCcw className="w-4 h-4 animate-spin" />
                <span>جارٍ فحص التكرار واختبار العشوائية...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>تشغيل كاشف البنية المجردة</span>
              </>
            )}
          </button>
          <span className="text-[10px] text-slate-500 block text-center mt-1 font-mono">
            {surrogateCount} تكرار مونت كارلو لفرضية العدم
          </span>
        </div>
      </div>

      {/* Main Timeline View */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-300">
          <span className="font-semibold flex items-center space-x-1.5">
            <Activity className="w-4 h-4 text-cyan-400" />
            <span>السلسلة الزمنية الكاملة وتحديد مواضع المقاطع المتطابقة:</span>
          </span>
          <span className="text-slate-400 font-mono text-[11px]">
            تم اكتشاف النمط في {result?.executionTimeMs} ميلي ثانية
          </span>
        </div>
        {renderTimelineSvg()}
      </div>

      {/* Results Sub-Tabs */}
      {result && (
        <div className="space-y-4">
          <div className="flex items-center space-x-1 bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs overflow-x-auto">
            <button
              onClick={() => setActiveSubTab('motifs')}
              className={`px-4 py-2 rounded-lg font-semibold transition-colors flex items-center space-x-1.5 cursor-pointer whitespace-nowrap ${
                activeSubTab === 'motifs'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>1. المقاطع المتكررة (Discovered Motifs)</span>
            </button>

            <button
              onClick={() => setActiveSubTab('surrogate')}
              className={`px-4 py-2 rounded-lg font-semibold transition-colors flex items-center space-x-1.5 cursor-pointer whitespace-nowrap ${
                activeSubTab === 'surrogate'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>2. اختبار الفرضية الصفرية (Surrogate Test)</span>
              {result.surrogateTest.isStatisticallySignificant ? (
                <span className="px-1.5 py-0.2 rounded text-[10px] bg-emerald-500/20 text-emerald-300 font-mono">
                  p &lt; 0.05
                </span>
              ) : (
                <span className="px-1.5 py-0.2 rounded text-[10px] bg-slate-700 text-slate-300 font-mono">
                  Noise
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveSubTab('intervals')}
              className={`px-4 py-2 rounded-lg font-semibold transition-colors flex items-center space-x-1.5 cursor-pointer whitespace-nowrap ${
                activeSubTab === 'intervals'
                  ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <TrendingDown className="w-4 h-4" />
              <span>3. تحليل الفواصل الزمنية (Interval Emergence)</span>
            </button>

            <button
              onClick={() => setActiveSubTab('raw_data')}
              className={`px-4 py-2 rounded-lg font-semibold transition-colors flex items-center space-x-1.5 cursor-pointer whitespace-nowrap ${
                activeSubTab === 'raw_data'
                  ? 'bg-slate-800 text-slate-200 border border-slate-700'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Info className="w-4 h-4" />
              <span>4. سجل البيانات الخام (Raw JSON & Provenance)</span>
            </button>
          </div>

          {/* TAB 1: MOTIFS */}
          {activeSubTab === 'motifs' && currentMotif && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Visual Overlay Chart */}
                <div className="space-y-2">
                  <h3 className="text-xs font-bold text-white flex items-center space-x-1.5">
                    <span>مقارنة تطابق الشكل بعد المعايرة (Z-Normalized Shape Overlay):</span>
                  </h3>
                  {renderMotifOverlaySvg()}
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    يتم تسوية كلا المقطعين رياضياً إلى متوسط صفري وانحراف معياري قدره 1.
                    هذا يعني أن المحرك يكتشف الشبه الهيكلي في مسار الصعود والهبوط حتى لو حدث المقطع الثاني عند مستويات سعرية أو تضخمية مختلفة تماماً.
                  </p>
                </div>

                {/* Details Card */}
                <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50 space-y-3 text-xs">
                  <h3 className="font-bold text-white flex items-center justify-between">
                    <span>خصائص النمط المكتشف (Motif Specification):</span>
                    <span className="font-mono text-cyan-400">{currentMotif.motifId}</span>
                  </h3>

                  <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
                    <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                      <span className="text-slate-400 block text-[10px]">المسافة الإقليدية (D):</span>
                      <strong className="text-cyan-300 text-sm">{currentMotif.distance}</strong>
                    </div>
                    <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                      <span className="text-slate-400 block text-[10px]">نسبة التشابه الهيكلي:</span>
                      <strong className="text-emerald-400 text-sm">{currentMotif.similarityPercentage}%</strong>
                    </div>
                  </div>

                  <div className="space-y-2 pt-2 border-t border-slate-800">
                    <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80">
                      <div className="text-cyan-400 font-semibold mb-1">الظهور الأول (Occurrence A):</div>
                      <div className="text-slate-300 font-mono text-[11px]">
                        الفترة: {currentMotif.occurrenceA.startDate} ← {currentMotif.occurrenceA.endDate} ({currentMotif.windowSize} نقاط)
                      </div>
                      <div className="text-slate-400 text-[10px] truncate mt-0.5">
                        القيم الأصلية: [{currentMotif.occurrenceA.rawValues.join(', ')}]
                      </div>
                    </div>

                    <div className="p-2.5 rounded-lg bg-slate-950/70 border border-slate-800/80">
                      <div className="text-amber-400 font-semibold mb-1">الظهور الثاني (Occurrence B):</div>
                      <div className="text-slate-300 font-mono text-[11px]">
                        الفترة: {currentMotif.occurrenceB.startDate} ← {currentMotif.occurrenceB.endDate} ({currentMotif.windowSize} نقاط)
                      </div>
                      <div className="text-slate-400 text-[10px] truncate mt-0.5">
                        القيم الأصلية: [{currentMotif.occurrenceB.rawValues.join(', ')}]
                      </div>
                    </div>
                  </div>

                  {currentMotif.allOccurrences && currentMotif.allOccurrences.length > 2 && (
                    <div className="p-2.5 rounded-lg bg-purple-950/20 border border-purple-800/30 text-purple-300 text-[11px]">
                      تم رصد {currentMotif.allOccurrences.length} فترات ظهور متوافقة مع هذا الهيكل عبر تاريخ السلسلة بالكامل.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: SURROGATE NULL TEST */}
          {activeSubTab === 'surrogate' && (
            <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-4 text-xs">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-amber-400" />
                    <span>اختبار الفرضية الصفرية لمونت كارلو (Surrogate Permutation Null Hypothesis)</span>
                  </h3>
                  <p className="text-slate-300 text-[11px] mt-0.5">
                    التحقق الصارم: هل تكرار هذا المقطع نتيجة نظامية غير عشوائية، أم يمكن إنتاجه بمجرد خلط أرقام السلسلة عشوائياً؟
                  </p>
                </div>
                <span
                  className={`px-3 py-1 rounded-full font-mono text-xs font-bold self-start md:self-center ${
                    result.surrogateTest.isStatisticallySignificant
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                  }`}
                >
                  {result.surrogateTest.isStatisticallySignificant ? '✓ بنية مثبتة إحصائياً' : '⚠ إشارة ضعيفة / عشوائية'}
                </span>
              </div>

              {/* 4 Metrics Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-slate-400 text-[10px] block">المسافة المرصودة في السلسلة الأصلية:</span>
                  <strong className="text-cyan-300 text-sm font-mono">{result.surrogateTest.observedMotifDistance}</strong>
                  <span className="text-[10px] text-slate-500 block mt-0.5">مسافة التكرار الحقيقية</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-slate-400 text-[10px] block">متوسط المسافات في البيانات العشوائية (Null Mean):</span>
                  <strong className="text-slate-200 text-sm font-mono">{result.surrogateTest.surrogateDistancesMean} ± {result.surrogateTest.surrogateDistancesStd}</strong>
                  <span className="text-[10px] text-slate-500 block mt-0.5">عبر {result.surrogateTest.permutationsCount} خلط عشوائي</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-slate-400 text-[10px] block">درجة الانحراف المعياري (Z-Score):</span>
                  <strong className={`text-sm font-mono ${result.surrogateTest.zScore >= 2.0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                    +{result.surrogateTest.zScore}σ
                  </strong>
                  <span className="text-[10px] text-slate-500 block mt-0.5">الابتعاد عن العشوائية التامة</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-slate-400 text-[10px] block">القيمة الاحتمالية (P-Value):</span>
                  <strong className={`text-sm font-mono ${result.surrogateTest.pValue < 0.05 ? 'text-emerald-400' : 'text-amber-400'}`}>
                    p = {result.surrogateTest.pValue}
                  </strong>
                  <span className="text-[10px] text-slate-500 block mt-0.5">
                    {result.surrogateTest.pValue < 0.05 ? 'دلالة إحصائية قوية' : 'فوق عتبة الدلالة'}
                  </span>
                </div>
              </div>

              {/* Scientific Verdict Card */}
              <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-1.5">
                <div className="font-bold text-white flex items-center space-x-2">
                  <Info className="w-4 h-4 text-cyan-400" />
                  <span>الحكم العلمي الصارم (Scientific Verdict):</span>
                </div>
                <p className="text-slate-300 text-xs leading-relaxed">
                  {result.surrogateTest.scientificNote}
                </p>
              </div>
            </div>
          )}

          {/* TAB 3: INTERVAL EMERGENCE */}
          {activeSubTab === 'intervals' && (
            <div className="p-5 rounded-2xl border border-slate-800 bg-slate-900/60 space-y-4 text-xs">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                  <TrendingDown className="w-4 h-4 text-purple-400" />
                  <span>تحليل الفواصل الزمنية وتطور النسب (Interval & Ratio Emergence)</span>
                </h3>
                <p className="text-slate-300 text-[11px] mt-0.5">
                  استخراج الفواصل الزمنية بين مرات ظهور النمط دون فرضية مسبقة، وقياس نسبة الفاصل اللاحق إلى السابق لمعرفة هل السلوك دوري منتظم أم منكمش أم متباعد.
                </p>
              </div>

              {result.intervalEmergence ? (
                <div className="space-y-4">
                  {/* Summary Bar */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <span className="text-slate-400 text-[10px] block">تصنيف السلوك الزمني:</span>
                      <strong className="text-purple-300 text-sm font-mono">
                        {result.intervalEmergence.classification}
                      </strong>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <span className="text-slate-400 text-[10px] block">متوسط الفاصل الزمني:</span>
                      <strong className="text-cyan-300 text-sm font-mono">
                        {(result.intervalEmergence.meanIntervalDays / 365.25).toFixed(1)} سنة ({result.intervalEmergence.meanIntervalDays} يوماً)
                      </strong>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                      <span className="text-slate-400 text-[10px] block">متوسط نسبة الفواصل (Δt_n+1 / Δt_n):</span>
                      <strong className="text-amber-300 text-sm font-mono">
                        {result.intervalEmergence.meanRatio.toFixed(3)} ± {result.intervalEmergence.ratioStdDev.toFixed(2)}
                      </strong>
                    </div>
                  </div>

                  {/* Occurrences Table */}
                  <div className="overflow-x-auto border border-slate-800 rounded-xl bg-slate-950/80">
                    <table className="w-full text-right font-mono text-[11px]">
                      <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="p-2.5">رقم الظهور</th>
                          <th className="p-2.5">تاريخ البداية</th>
                          <th className="p-2.5">الفاصل الزمني عن السابق (Δt)</th>
                          <th className="p-2.5">النسبة إلى الفاصل السابق (r_n)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 text-slate-200">
                        {result.intervalEmergence.timestamps.map((date, idx) => {
                          const delta = idx > 0 && result.intervalEmergence ? result.intervalEmergence.rawIntervalsDays[idx - 1] : undefined;
                          const ratio = idx > 1 && result.intervalEmergence ? result.intervalEmergence.intervalRatios[idx - 2] : undefined;
                          return (
                            <tr key={date} className="hover:bg-slate-900/40">
                              <td className="p-2.5 text-slate-400">#{idx + 1}</td>
                              <td className="p-2.5 text-cyan-300 font-bold">{date}</td>
                              <td className="p-2.5">
                                {typeof delta === 'number' ? `${delta} يوماً (${(delta / 365.25).toFixed(1)} سنة)` : '— (نقطة البداية)'}
                              </td>
                              <td className="p-2.5">
                                {typeof ratio === 'number' ? (
                                  <span className="text-amber-400 font-bold">{ratio.toFixed(3)}</span>
                                ) : (
                                  '—'
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Narrative Diagnosis */}
                  <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800/80">
                    <div className="font-bold text-white mb-1">التقرير الرياضي للمحرك:</div>
                    <p className="text-slate-300 leading-relaxed text-xs">
                      {result.intervalEmergence.candidateFormulaDescription}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="p-6 text-center text-slate-400 border border-slate-800 rounded-xl bg-slate-950">
                  لم يتم رصد فواصل زمنية كافية (يتطلب تكرار النمط مرتين على الأقل في السلسلة الحالية لحساب الفواصل).
                </div>
              )}
            </div>
          )}

          {/* TAB 4: RAW DATA */}
          {activeSubTab === 'raw_data' && (
            <div className="p-4 rounded-2xl border border-slate-800 bg-slate-950 space-y-3 text-xs font-mono">
              <div className="flex items-center justify-between text-slate-400">
                <span>سجل المخرجات البرمجية الخام (Raw Discovery Payload):</span>
                <span>JSON Object</span>
              </div>
              <pre className="p-4 rounded-xl bg-slate-900 text-slate-300 text-[11px] overflow-x-auto max-h-96 border border-slate-800/80 leading-relaxed">
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Custom Input Modal */}
      {showCustomModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Upload className="w-4 h-4 text-cyan-400" />
                <span>إدخال بيانات سلسلة زمنية مخصصة</span>
              </h3>
              <button
                onClick={() => setShowCustomModal(false)}
                className="text-slate-400 hover:text-white text-xs cursor-pointer font-bold"
              >
                ✕ إغلاق
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              أدخل البيانات على شكل أسطر، كل سطر يحتوي على: <code className="text-cyan-300">التاريخ, القيمة</code> (مثال: <code className="text-slate-400">2010-01-01, 15.4</code>). الحد الأدنى 16 نقطة.
            </p>

            <textarea
              rows={8}
              value={customInputText}
              onChange={(e) => setCustomInputText(e.target.value)}
              placeholder={`1990-01-01, 10.2\n1991-01-01, 12.5\n1992-01-01, 8.4\n1993-01-01, 14.1\n...`}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
            />

            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                onClick={() => setShowCustomModal(false)}
                className="px-4 py-2 rounded-xl text-slate-400 hover:text-slate-200 text-xs font-semibold cursor-pointer"
              >
                إلغاء
              </button>
              <button
                onClick={handleParseCustomData}
                className="px-5 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs cursor-pointer"
              >
                معالجة وتشغيل الكشف
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
