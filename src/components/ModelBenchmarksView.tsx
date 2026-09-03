import React, { useState } from 'react';
import { MODEL_BENCHMARKS, VARIABLE_IMPORTANCE_RANKINGS } from '../data/chaosData';
import { Activity, BarChart2, TrendingUp, Layers, CheckCircle2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export const ModelBenchmarksView: React.FC = () => {
  const [selectedMetric, setSelectedMetric] = useState<'test_mae' | 'val_loss'>('test_mae');

  // Chart data for model comparison
  const chartData = MODEL_BENCHMARKS.map((m) => ({
    name: m.name.replace('Temporal Fusion Transformer', 'TFT').replace('Baseline', 'Base'),
    mae: Number(m.test_mae.toFixed(3)),
    valLoss: Number(m.val_loss.toFixed(3)),
    status: m.status
  }));

  const sortedImportance = [...VARIABLE_IMPORTANCE_RANKINGS].sort((a, b) => b.importance - a.importance);

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <span className="text-xs font-mono text-slate-400">BEST MODEL</span>
          <div className="mt-2 flex items-baseline justify-between">
            <h3 className="text-xl font-bold font-mono text-cyan-300">TFT V1.1</h3>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              CONVERGED
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Temporal Fusion Transformer with quantile loss
          </p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <span className="text-xs font-mono text-slate-400">TEST MAE IMPROVEMENT</span>
          <div className="mt-2 flex items-baseline justify-between">
            <h3 className="text-xl font-bold font-mono text-emerald-300">+3.24%</h3>
            <TrendingUp className="w-5 h-5 text-emerald-400" />
          </div>
          <p className="mt-1 text-xs text-slate-400">
            3.936 MAE vs 4.068 (Best Baseline: Global Mean)
          </p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <span className="text-xs font-mono text-slate-400">DIRECTIONAL ACCURACY</span>
          <div className="mt-2 flex items-baseline justify-between">
            <h3 className="text-xl font-bold font-mono text-cyan-300">77.41%</h3>
            <Activity className="w-5 h-5 text-cyan-400" />
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Correct directional swing sign prediction
          </p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <span className="text-xs font-mono text-slate-400">CHRONOLOGICAL SPLIT</span>
          <div className="mt-2 flex items-baseline justify-between">
            <h3 className="text-xl font-bold font-mono text-indigo-300">2020-2024</h3>
            <Layers className="w-5 h-5 text-indigo-400" />
          </div>
          <p className="mt-1 text-xs text-slate-400">
            N=695 test window samples; zero leakage
          </p>
        </div>
      </div>

      {/* Model Benchmark Comparison Table & Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800">
            <div>
              <h3 className="text-base font-semibold text-slate-100 flex items-center space-x-2">
                <BarChart2 className="w-4 h-4 text-cyan-400" />
                <span>Model & Ablation Performance Leaderboard</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Ordered by Test Mean Absolute Error (MAE) on locked 2020-2024 holdout split.
              </p>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => setSelectedMetric('test_mae')}
                className={`px-2.5 py-1 text-xs font-mono rounded ${
                  selectedMetric === 'test_mae'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Test MAE
              </button>
              <button
                onClick={() => setSelectedMetric('val_loss')}
                className={`px-2.5 py-1 text-xs font-mono rounded ${
                  selectedMetric === 'val_loss'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Val Loss
              </button>
            </div>
          </div>

          <div className="overflow-x-auto mt-4">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 font-mono border-b border-slate-800">
                <tr>
                  <th className="p-2.5">Model / Architecture</th>
                  <th className="p-2.5">Type</th>
                  <th className="p-2.5">Val Loss</th>
                  <th className="p-2.5">Test MAE</th>
                  <th className="p-2.5">p10 / p90 Spread</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {MODEL_BENCHMARKS.map((m) => (
                  <tr
                    key={m.model_id}
                    className={`hover:bg-slate-800/30 ${
                      m.model_id === 'TFT_V1_1_BEST' ? 'bg-cyan-500/5' : ''
                    }`}
                  >
                    <td className="p-2.5 font-sans font-medium text-slate-200">
                      <div className="flex items-center space-x-1.5">
                        {m.model_id === 'TFT_V1_1_BEST' && (
                          <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                        )}
                        <span>{m.name}</span>
                      </div>
                      <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
                        {m.notes}
                      </span>
                    </td>
                    <td className="p-2.5">
                      <span className={`text-[10px] px-2 py-0.5 rounded border uppercase ${
                        m.status === 'converged'
                          ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/20'
                          : m.status === 'baseline'
                          ? 'bg-slate-800 text-slate-300 border-slate-700'
                          : 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20'
                      }`}>
                        {m.status}
                      </span>
                    </td>
                    <td className="p-2.5 text-slate-300">{m.val_loss.toFixed(4)}</td>
                    <td className="p-2.5 font-bold text-cyan-300">{m.test_mae.toFixed(4)}</td>
                    <td className="p-2.5 text-slate-400 text-[11px]">
                      {m.p10_loss.toFixed(2)} - {m.p90_loss.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Visual Comparison Chart */}
        <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-100 mb-1">
              Error Metric Comparison
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Lower is better. Comparison of {selectedMetric === 'test_mae' ? 'Test MAE' : 'Validation Loss'} across models.
            </p>

            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                  <XAxis
                    type="number"
                    domain={selectedMetric === 'test_mae' ? [3.5, 4.8] : [1.4, 2.2]}
                    stroke="#64748b"
                    fontSize={11}
                    fontFamily="monospace"
                  />
                  <YAxis
                    dataKey="name"
                    type="category"
                    stroke="#94a3b8"
                    fontSize={10}
                    width={100}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                    labelStyle={{ color: '#f8fafc', fontWeight: 'bold' }}
                  />
                  <Bar
                    dataKey={selectedMetric === 'test_mae' ? 'mae' : 'valLoss'}
                    radius={[0, 4, 4, 0]}
                  >
                    {chartData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.status === 'converged' ? '#06b6d4' : entry.status === 'baseline' ? '#64748b' : '#818cf8'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800 text-[11px] font-mono text-slate-400 flex items-center justify-between">
            <span className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded bg-cyan-500"></span>
              <span>Primary TFT</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded bg-slate-500"></span>
              <span>Heuristic Baselines</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="w-2.5 h-2.5 rounded bg-indigo-500"></span>
              <span>Feature Ablations</span>
            </span>
          </div>
        </div>
      </div>

      {/* Feature Importance Rankings */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-base font-semibold text-slate-100 flex items-center space-x-2">
          <Layers className="w-4 h-4 text-cyan-400" />
          <span>TFT Variable Selection Network Importance Rankings</span>
        </h3>
        <p className="text-xs text-slate-400 mt-0.5 mb-4">
          Relative attention weight assigned by the encoder Variable Selection Network (VSN) across macro and energy series.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sortedImportance.map((v) => (
            <div
              key={v.variable}
              className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg flex flex-col justify-between space-y-2"
            >
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-slate-200">{v.variable}</span>
                  <span className="text-[10px] font-mono text-slate-400 block">Source: {v.source}</span>
                </div>
                <span className="text-xs font-mono font-bold text-cyan-300">
                  {(v.importance * 100).toFixed(1)}%
                </span>
              </div>

              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-cyan-400 h-1.5 rounded-full"
                  style={{ width: `${(v.importance / 0.3) * 100}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
