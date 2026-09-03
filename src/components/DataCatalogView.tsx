import React, { useState } from 'react';
import { DATA_READINESS_METRICS } from '../data/chaosData';
import { Database, Filter, CheckCircle2, AlertCircle, BarChart2 } from 'lucide-react';

const SAMPLE_ENTITIES = [
  { code: 'USA', name: 'United States', wdi: true, weo: true, eia: true, complete: true },
  { code: 'DEU', name: 'Germany', wdi: true, weo: true, eia: true, complete: true },
  { code: 'JPN', name: 'Japan', wdi: true, weo: true, eia: true, complete: true },
  { code: 'GBR', name: 'United Kingdom', wdi: true, weo: true, eia: true, complete: true },
  { code: 'FRA', name: 'France', wdi: true, weo: true, eia: true, complete: true },
  { code: 'IND', name: 'India', wdi: true, weo: true, eia: true, complete: true },
  { code: 'BRA', name: 'Brazil', wdi: true, weo: true, eia: true, complete: true },
  { code: 'ZAF', name: 'South Africa', wdi: true, weo: true, eia: true, complete: true },
  { code: 'KOR', name: 'South Korea', wdi: true, weo: true, eia: true, complete: true },
  { code: 'MEX', name: 'Mexico', wdi: true, weo: true, eia: true, complete: true },
  { code: 'EGY', name: 'Egypt', wdi: true, weo: true, eia: true, complete: true },
  { code: 'SAU', name: 'Saudi Arabia', wdi: true, weo: true, eia: true, complete: true },
  { code: 'SOM', name: 'Somalia', wdi: true, weo: false, eia: false, complete: false },
  { code: 'PRK', name: 'North Korea', wdi: false, weo: false, eia: true, complete: false },
  { code: 'SSD', name: 'South Sudan', wdi: true, weo: true, eia: false, complete: false }
];

export const DataCatalogView: React.FC = () => {
  const [filterComplete, setFilterComplete] = useState<boolean>(false);
  const [searchEntity, setSearchEntity] = useState<string>('');

  const filteredEntities = SAMPLE_ENTITIES.filter((e) => {
    if (filterComplete && !e.complete) return false;
    if (searchEntity && !e.name.toLowerCase().includes(searchEntity.toLowerCase()) && !e.code.toLowerCase().includes(searchEntity.toLowerCase())) {
      return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Readiness Overview */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <Database className="w-5 h-5 text-cyan-400" />
              <h2 className="text-base font-bold text-slate-100">Annual Panel Data Readiness Gate</h2>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                {DATA_READINESS_METRICS.gate_status}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Audit of raw historical coverage spanning 2000–2024 (25 years) across World Bank WDI, IMF WEO, and EIA.
            </p>
          </div>
        </div>

        {/* Readiness Key Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <span className="text-[11px] font-mono text-slate-400 block">TOTAL CELLS AUDITED</span>
            <span className="text-lg font-bold font-mono text-slate-100">
              {DATA_READINESS_METRICS.total_cells_audited.toLocaleString()}
            </span>
          </div>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <span className="text-[11px] font-mono text-slate-400 block">NON-EMPTY CELLS</span>
            <span className="text-lg font-bold font-mono text-emerald-400">
              {DATA_READINESS_METRICS.nonempty_cells.toLocaleString()}
            </span>
          </div>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <span className="text-[11px] font-mono text-slate-400 block">PRESERVED NULL CELLS</span>
            <span className="text-lg font-bold font-mono text-amber-400">
              {DATA_READINESS_METRICS.missing_cells_preserved_null.toLocaleString()}
            </span>
          </div>
          <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
            <span className="text-[11px] font-mono text-slate-400 block">STRICT CLEAN ENTITIES</span>
            <span className="text-lg font-bold font-mono text-cyan-300">
              {DATA_READINESS_METRICS.strict_complete_numeric}
            </span>
          </div>
        </div>
      </div>

      {/* Coverage Funnel Breakdown */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-base font-semibold text-slate-100 flex items-center space-x-2">
          <BarChart2 className="w-4 h-4 text-cyan-400" />
          <span>Entity Attrition & Selection Funnel</span>
        </h3>
        <p className="text-xs text-slate-400 mt-0.5 mb-4">
          Zero imputation is applied. Countries missing continuous historical records across the 25-year panel are systematically isolated.
        </p>

        <div className="space-y-3">
          {DATA_READINESS_METRICS.breakdown.map((step, idx) => (
            <div key={idx} className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg">
              <div className="flex items-center justify-between text-xs font-mono mb-1.5">
                <span className="text-slate-300">{step.stage}</span>
                <span className="font-bold text-cyan-300">{step.count} entities ({step.pct}%)</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-cyan-500 h-2 rounded-full transition-all"
                  style={{ width: `${step.pct}%` }}
                ></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Entity Retention Sample Inspector */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-base font-semibold text-slate-100 flex items-center space-x-2">
              <Filter className="w-4 h-4 text-cyan-400" />
              <span>Sample Entity Retention Directory</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Auditable breakdown of source-specific indicator availability for sample global economies.
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <input
              type="text"
              placeholder="Search code or country..."
              value={searchEntity}
              onChange={(e) => setSearchEntity(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
            />
            <button
              onClick={() => setFilterComplete(!filterComplete)}
              className={`px-3 py-1 rounded-lg text-xs font-mono border transition ${
                filterComplete
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                  : 'bg-slate-950 text-slate-400 border-slate-800'
              }`}
            >
              {filterComplete ? 'Showing Clean Only' : 'Show All'}
            </button>
          </div>
        </div>

        <div className="overflow-x-auto border border-slate-800 rounded-lg">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 text-slate-400 font-mono border-b border-slate-800">
              <tr>
                <th className="p-2.5">Code</th>
                <th className="p-2.5">Country / Entity</th>
                <th className="p-2.5 text-center">World Bank (WDI)</th>
                <th className="p-2.5 text-center">IMF (WEO)</th>
                <th className="p-2.5 text-center">US EIA Energy</th>
                <th className="p-2.5 text-center">Strict Panel Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filteredEntities.map((item) => (
                <tr key={item.code} className="hover:bg-slate-800/30">
                  <td className="p-2.5 font-bold text-cyan-300">{item.code}</td>
                  <td className="p-2.5 text-slate-200 font-sans">{item.name}</td>
                  <td className="p-2.5 text-center">
                    {item.wdi ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 inline" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-slate-600 inline" />
                    )}
                  </td>
                  <td className="p-2.5 text-center">
                    {item.weo ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 inline" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-slate-600 inline" />
                    )}
                  </td>
                  <td className="p-2.5 text-center">
                    {item.eia ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 inline" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-slate-600 inline" />
                    )}
                  </td>
                  <td className="p-2.5 text-center">
                    <span className={`text-[10px] px-2 py-0.5 rounded border ${
                      item.complete
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}>
                      {item.complete ? 'ADMITTED' : 'EXCLUDED (GAPS)'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
