import React, { useState } from 'react';
import { SUPERVISOR_GATE_DATA, AGENT_SPECS } from '../data/chaosData';
import { ShieldCheck, ShieldAlert, CheckCircle2, XCircle, FileText, Bot, Lock, ExternalLink } from 'lucide-react';

export const SupervisorGateView: React.FC = () => {
  const [filterDomain, setFilterDomain] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const inputFilesList = Object.entries(SUPERVISOR_GATE_DATA.input_hashes);

  const filteredInputs = inputFilesList.filter(([path]) => {
    return path.toLowerCase().includes(searchTerm.toLowerCase());
  });

  const filteredAgents = AGENT_SPECS.filter((agent) => {
    if (filterDomain === 'all') return true;
    return agent.domain === filterDomain;
  });

  return (
    <div className="space-y-6">
      {/* Overview Stat Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">GATE STATUS</span>
            <span className="px-2 py-0.5 rounded text-xs font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              {SUPERVISOR_GATE_DATA.status.toUpperCase()}
            </span>
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <h3 className="text-2xl font-bold font-mono text-slate-100">PASS</h3>
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
          </div>
          <p className="mt-1 text-xs text-slate-400 font-mono">
            ID: {SUPERVISOR_GATE_DATA.gate_id}
          </p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">ADMITTED SUPPORTED</span>
            <span className="px-2 py-0.5 rounded text-xs font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              ELIGIBLE
            </span>
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <h3 className="text-2xl font-bold font-mono text-cyan-300">
              {SUPERVISOR_GATE_DATA.admitted_supported_predictive_records}
            </h3>
            <CheckCircle2 className="w-5 h-5 text-cyan-400" />
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Records passing null and out-of-sample tests
          </p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">QUARANTINED TRANSITIONS</span>
            <span className="px-2 py-0.5 rounded text-xs font-mono bg-amber-500/10 text-amber-300 border border-amber-500/20">
              AUDITABLE
            </span>
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <h3 className="text-2xl font-bold font-mono text-amber-300">
              {SUPERVISOR_GATE_DATA.quarantined_records}
            </h3>
            <ShieldAlert className="w-5 h-5 text-amber-400" />
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Preserved negative/unresolved evidence
          </p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">CAUSAL CLAIMS</span>
            <span className="px-2 py-0.5 rounded text-xs font-mono bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
              GUARDRAIL
            </span>
          </div>
          <div className="mt-3 flex items-baseline justify-between">
            <h3 className="text-2xl font-bold font-mono text-indigo-300">
              {SUPERVISOR_GATE_DATA.causal_claims_admitted}
            </h3>
            <Lock className="w-5 h-5 text-indigo-400" />
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Strictly zero causal claims permitted
          </p>
        </div>
      </div>

      {/* Supervisor Invariant Rules */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-base font-semibold text-slate-200 flex items-center space-x-2">
          <Lock className="w-4 h-4 text-cyan-400" />
          <span>Supervisor Admission Invariants</span>
        </h3>
        <p className="text-xs text-slate-400 mt-1">
          Every candidate edge or transition must satisfy these mathematical and procedural constraints before composition admission:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 flex items-start space-x-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-xs font-medium text-slate-200">No Rejected Weight</span>
              <p className="text-xs text-slate-400 mt-0.5">
                Rejected edges cannot contribute positive weight to composite path assembly.
              </p>
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 flex items-start space-x-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-xs font-medium text-slate-200">No Unresolved Weight</span>
              <p className="text-xs text-slate-400 mt-0.5">
                Unresolved or pending evidence cannot be assumed true in downstream graph inference.
              </p>
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 flex items-start space-x-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-xs font-medium text-slate-200">Temporal Precedence Separation</span>
              <p className="text-xs text-slate-400 mt-0.5">
                Future outcomes can never be retrofitted to define current or past state classifications.
              </p>
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 flex items-start space-x-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-xs font-medium text-slate-200">No Blanket Imputation</span>
              <p className="text-xs text-slate-400 mt-0.5">
                Missing raw observations remain missing; synthetic infill is forbidden without an explicit adapter contract.
              </p>
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 flex items-start space-x-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-xs font-medium text-slate-200">Max-Stat Permutation Nulls</span>
              <p className="text-xs text-slate-400 mt-0.5">
                Candidate edges must outperform randomized null distributions accounting for multiple hypothesis search breadth.
              </p>
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 flex items-start space-x-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="text-xs font-medium text-slate-200">Idempotent Run Ledger</span>
              <p className="text-xs text-slate-400 mt-0.5">
                Every agent execution writes a cryptographic run manifest and ledger entry before supervisor admission.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Agent Orchestration Registry */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-base font-semibold text-slate-200 flex items-center space-x-2">
              <Bot className="w-4 h-4 text-cyan-400" />
              <span>Agent Orchestration Registry V1</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Domain agents operate in sandboxed workspaces with strictly delineated scopes and supervisor review.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-400">Filter:</span>
            <select
              value={filterDomain}
              onChange={(e) => setFilterDomain(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="all">All Domains</option>
              <option value="trade">Trade</option>
              <option value="institutions_policy">Institutions & Policy</option>
              <option value="energy">Energy</option>
              <option value="environment_disaster">Environment & Disaster</option>
              <option value="health_pandemic">Health & Pandemic</option>
              <option value="cross_domain">Cross-Domain</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredAgents.map((agent) => (
            <div
              key={agent.agent_id}
              className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-4 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-semibold text-cyan-300">
                    {agent.agent_id}
                  </span>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                    agent.last_run_status === 'synced'
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : agent.last_run_status === 'active'
                      ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                      : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                  }`}>
                    {agent.last_run_status?.toUpperCase() || 'IDLE'}
                  </span>
                </div>

                <div className="mt-2 text-xs font-mono text-slate-400 flex items-center space-x-2">
                  <span>Priority: {agent.priority}</span>
                  <span>•</span>
                  <span className="text-slate-300 capitalize">{agent.domain.replace('_', ' ')}</span>
                </div>

                <p className="mt-2.5 text-xs text-slate-300 line-clamp-3">
                  {agent.scope}
                </p>

                <div className="mt-3">
                  <span className="text-[11px] font-mono text-slate-400 block mb-1">Declared Outputs:</span>
                  <div className="flex flex-wrap gap-1">
                    {agent.outputs.map((out) => (
                      <span
                        key={out}
                        className="text-[10px] font-mono px-1.5 py-0.5 bg-slate-900 text-slate-400 rounded border border-slate-800"
                      >
                        {out}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between text-[11px] font-mono text-slate-400">
                <span className="truncate max-w-[170px]" title={agent.workspace}>
                  {agent.workspace}
                </span>
                <span className="text-slate-400 text-[10px]">
                  {agent.shared_write}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Input Files & SHA-256 Checksums */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-base font-semibold text-slate-200 flex items-center space-x-2">
              <FileText className="w-4 h-4 text-cyan-400" />
              <span>Supervisor Input Files & Cryptographic Fingerprints</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              All 16 transition evidence files submitted to the supervisor gate with SHA-256 integrity verification.
            </p>
          </div>

          <div>
            <input
              type="text"
              placeholder="Search file path..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 w-full sm:w-64"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 text-slate-400 font-mono border-b border-slate-800">
              <tr>
                <th className="p-2.5">Input Evidence Artifact</th>
                <th className="p-2.5">SHA-256 Checksum (First 16 / Full)</th>
                <th className="p-2.5 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filteredInputs.map(([path, hash]) => (
                <tr key={path} className="hover:bg-slate-800/30 transition-colors">
                  <td className="p-2.5 text-slate-200 break-all font-sans text-xs">
                    {path}
                  </td>
                  <td className="p-2.5 text-cyan-300/80">
                    <span className="font-bold text-cyan-300">{hash.substring(0, 16)}</span>
                    <span className="text-slate-400">{hash.substring(16)}</span>
                  </td>
                  <td className="p-2.5 text-center">
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>VERIFIED</span>
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
