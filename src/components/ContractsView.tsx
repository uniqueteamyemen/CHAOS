import React, { useState } from 'react';
import { EXPERIMENTAL_CONTRACTS } from '../data/chaosData';
import { Lock, FileCheck, AlertOctagon, CheckCircle2, Info, ChevronRight, Layers } from 'lucide-react';

export const ContractsView: React.FC = () => {
  const [selectedContractId, setSelectedContractId] = useState<string>(
    EXPERIMENTAL_CONTRACTS[0].id
  );

  const contract =
    EXPERIMENTAL_CONTRACTS.find((c) => c.id === selectedContractId) ||
    EXPERIMENTAL_CONTRACTS[0];

  return (
    <div className="space-y-6">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-100 flex items-center space-x-2">
              <Lock className="w-5 h-5 text-cyan-400" />
              <span>Governed Experimental Contracts</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Contracts define immutable pre-registration parameters, variable boundaries, and validation criteria before any empirical test is initiated.
            </p>
          </div>
          <div className="text-xs font-mono px-3 py-1 bg-slate-950 border border-slate-800 rounded-lg text-slate-400">
            Active Registered Contracts: {EXPERIMENTAL_CONTRACTS.length}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Contract Selector Sidebar */}
        <div className="lg:col-span-4 space-y-3">
          {EXPERIMENTAL_CONTRACTS.map((item) => {
            const isSelected = item.id === selectedContractId;
            return (
              <button
                key={item.id}
                onClick={() => setSelectedContractId(item.id)}
                className={`w-full text-left p-4 rounded-xl border transition-all ${
                  isSelected
                    ? 'bg-cyan-500/10 border-cyan-500/40 shadow-sm'
                    : 'bg-slate-900/90 border-slate-800 hover:border-slate-700 hover:bg-slate-850'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase ${
                    item.status === 'review_only'
                      ? 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                      : item.status === 'frozen'
                      ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20'
                      : 'bg-rose-500/10 text-rose-300 border-rose-500/20'
                  }`}>
                    {item.status.replace('_', ' ')}
                  </span>
                  <span className="text-xs font-mono text-slate-400">{item.timeframe}</span>
                </div>

                <h3 className={`mt-2 text-sm font-semibold ${isSelected ? 'text-cyan-200' : 'text-slate-200'}`}>
                  {item.title}
                </h3>
                <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                  {item.description}
                </p>

                <div className="mt-3 flex items-center justify-between text-xs font-mono text-slate-400 border-t border-slate-800/60 pt-2">
                  <span>{item.authorized_variables.length} Authorized Vars</span>
                  <ChevronRight className={`w-3.5 h-3.5 ${isSelected ? 'text-cyan-400' : 'text-slate-600'}`} />
                </div>
              </button>
            );
          })}
        </div>

        {/* Contract Detail Panel */}
        <div className="lg:col-span-8 space-y-5">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
              <div>
                <span className="text-xs font-mono text-cyan-400">{contract.id}</span>
                <h2 className="text-xl font-bold text-slate-100 mt-0.5">{contract.title}</h2>
              </div>
              <div className="flex items-center space-x-2">
                <span className="px-2.5 py-1 rounded text-xs font-mono bg-slate-950 border border-slate-800 text-slate-300">
                  Version: {contract.version}
                </span>
                <span className={`px-2.5 py-1 rounded text-xs font-mono border uppercase ${
                  contract.status === 'review_only'
                    ? 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                    : contract.status === 'frozen'
                    ? 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20'
                    : 'bg-rose-500/10 text-rose-300 border-rose-500/20'
                }`}>
                  {contract.status.replace('_', ' ')}
                </span>
              </div>
            </div>

            {/* Scope Details */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 my-5 py-3 px-4 bg-slate-950/60 rounded-lg border border-slate-800">
              <div>
                <span className="text-[11px] font-mono text-slate-400 block">Domain</span>
                <span className="text-xs font-semibold text-slate-200">{contract.domain}</span>
              </div>
              <div>
                <span className="text-[11px] font-mono text-slate-400 block">Frequency</span>
                <span className="text-xs font-semibold text-slate-200">{contract.frequency}</span>
              </div>
              <div>
                <span className="text-[11px] font-mono text-slate-400 block">Time Horizon</span>
                <span className="text-xs font-semibold text-slate-200">{contract.timeframe}</span>
              </div>
            </div>

            {/* Hypothesis Box */}
            <div className="space-y-2">
              <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                <Info className="w-3.5 h-3.5 text-cyan-400" />
                <span>Pre-Registered Empirical Hypothesis</span>
              </h4>
              <p className="text-xs text-slate-200 bg-slate-950/80 border border-slate-800 rounded-lg p-3 leading-relaxed">
                {contract.hypothesis}
              </p>
            </div>

            {/* Guardrails Box */}
            <div className="space-y-2 mt-5">
              <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                <AlertOctagon className="w-3.5 h-3.5 text-amber-400" />
                <span>Contractual Guardrails & Prohibitions</span>
              </h4>
              <ul className="space-y-2">
                {contract.guardrails.map((rule, idx) => (
                  <li
                    key={idx}
                    className="text-xs text-slate-300 bg-slate-950/50 border border-slate-800/80 rounded-lg p-2.5 flex items-start space-x-2"
                  >
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{rule}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Authorized Variables Table */}
            <div className="space-y-3 mt-6">
              <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                <span>Authorized Variable Catalog ({contract.authorized_variables.length})</span>
              </h4>

              <div className="overflow-x-auto border border-slate-800 rounded-lg">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 text-slate-400 font-mono border-b border-slate-800">
                    <tr>
                      <th className="p-2.5">Variable Name</th>
                      <th className="p-2.5">Source Provider</th>
                      <th className="p-2.5">Source Identifier Code</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {contract.authorized_variables.map((v, i) => (
                      <tr key={i} className="hover:bg-slate-800/30">
                        <td className="p-2.5 text-slate-200 font-sans text-xs">
                          {v.name}
                        </td>
                        <td className="p-2.5 text-cyan-300">
                          {v.source}
                        </td>
                        <td className="p-2.5 text-slate-400">
                          {v.code}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
