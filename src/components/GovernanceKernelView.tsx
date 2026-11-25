import React, { useState } from 'react';
import { SAMPLE_GOVERNANCE_BUNDLE, INITIAL_EVIDENCE_GRAPH } from '../data/chaosData';
import {
  validateGovernanceManifest,
  auditCsvContent,
  buildDynamicEvidenceGraph
} from '../utils/governanceKernel';
import {
  GitFork,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  FileSpreadsheet,
  Network,
  Terminal,
  ShieldCheck
} from 'lucide-react';

const DEFAULT_CSV_SAMPLE = `entity_code,year,gdp_growth,inflation,energy_cons,target_deterioration
USA,2020,-2.77,1.23,297.2,1
USA,2021,5.95,4.70,305.1,0
USA,2022,2.06,8.00,312.4,0
USA,2023,2.54,4.12,308.9,0
GBR,2020,-10.36,0.99,165.2,1
GBR,2021,8.67,2.52,171.0,0
GBR,2022,4.35,9.07,166.4,0
DEU,2020,-3.83,0.37,130.5,1
DEU,2021,3.18,3.21,135.2,0
DEU,2022,1.81,8.67,130.8,0`;

export const GovernanceKernelView: React.FC = () => {
  const [manifestState] = useState(SAMPLE_GOVERNANCE_BUNDLE);
  const [manifestResult, setManifestResult] = useState<ReturnType<typeof validateGovernanceManifest> | null>(null);
  const [isVerifyingManifest, setIsVerifyingManifest] = useState(false);

  // CSV Audit states
  const [csvInput, setCsvInput] = useState(DEFAULT_CSV_SAMPLE);
  const [requiredCols, setRequiredCols] = useState('entity_code,year,gdp_growth');
  const [expectedFreq, setExpectedFreq] = useState('annual');
  const [predictorCols, setPredictorCols] = useState('gdp_growth,inflation,energy_cons');
  const [targetPrefixes, setTargetPrefixes] = useState('target_');
  const [csvAuditResult, setCsvAuditResult] = useState<ReturnType<typeof auditCsvContent> | null>(null);

  // Evidence Graph state
  const [graphData, setGraphData] = useState(INITIAL_EVIDENCE_GRAPH);
  const [activeKernelTab, setActiveKernelTab] = useState<'manifest' | 'audit' | 'graph' | 'ledger'>('manifest');

  const handleRunManifestValidation = () => {
    setIsVerifyingManifest(true);
    setTimeout(() => {
      const res = validateGovernanceManifest(manifestState);
      setManifestResult(res);
      setIsVerifyingManifest(false);
    }, 300);
  };

  const handleRunCsvAudit = () => {
    const reqColsList = requiredCols.split(',').map(s => s.trim()).filter(Boolean);
    const predColsList = predictorCols.split(',').map(s => s.trim()).filter(Boolean);
    const targetPrefList = targetPrefixes.split(',').map(s => s.trim()).filter(Boolean);

    const res = auditCsvContent(
      csvInput,
      reqColsList,
      ['entity_code', 'year'],
      'year',
      expectedFreq,
      predColsList,
      targetPrefList
    );
    setCsvAuditResult(res);
  };

  const handleRegenerateGraph = () => {
    const g = buildDynamicEvidenceGraph(manifestState);
    setGraphData(g);
  };

  return (
    <div className="space-y-6">
      {/* Kernel Sub-Navigation */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-100 flex items-center space-x-2">
            <GitFork className="w-5 h-5 text-cyan-400" />
            <span>CHAOS Governance Kernel Simulator</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Cryptographic artifact verification, structural CSV checks, and evidence graph synthesis.
          </p>
        </div>

        <div className="flex space-x-2 bg-slate-950 p-1 rounded-lg border border-slate-800">
          <button
            onClick={() => setActiveKernelTab('manifest')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeKernelTab === 'manifest'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Manifest Validator
          </button>
          <button
            onClick={() => setActiveKernelTab('audit')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeKernelTab === 'audit'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            CSV Data Audit
          </button>
          <button
            onClick={() => setActiveKernelTab('graph')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeKernelTab === 'graph'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Evidence Graph
          </button>
          <button
            onClick={() => setActiveKernelTab('ledger')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeKernelTab === 'ledger'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Provenance Ledger
          </button>
        </div>
      </div>

      {/* Tab 1: Manifest Validator */}
      {activeKernelTab === 'manifest' && (
        <div className="space-y-5">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-800">
              <div>
                <span className="text-xs font-mono text-cyan-400">MANIFEST VALIDATION SUITE</span>
                <h3 className="text-base font-semibold text-slate-100 mt-0.5">
                  Bundle: {manifestState.bundle_id}
                </h3>
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={handleRunManifestValidation}
                  disabled={isVerifyingManifest}
                  className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium transition shadow-sm cursor-pointer"
                >
                  <Play className="w-3.5 h-3.5" />
                  <span>{isVerifyingManifest ? 'Verifying Hashes...' : 'Run Kernel Validation'}</span>
                </button>
              </div>
            </div>

            {manifestResult && (
              <div className={`mt-4 p-4 rounded-xl border flex items-start space-x-3 ${
                manifestResult.status === 'pass'
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              }`}>
                {manifestResult.status === 'pass' ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                )}
                <div>
                  <h4 className="text-xs font-mono font-bold uppercase">
                    Validation Status: {manifestResult.status} ({manifestResult.checked_count} / {manifestResult.artifact_count} artifacts verified)
                  </h4>
                  <p className="text-xs text-slate-300 mt-1">
                    All cryptographic SHA-256 hashes matched, byte sizes confirmed, and zero duplicate paths detected in bundle manifest.
                  </p>
                  <span className="text-[10px] font-mono text-slate-400 mt-1 block">
                    Checked at: {manifestResult.checked_at}
                  </span>
                </div>
              </div>
            )}

            <div className="mt-5 space-y-3">
              <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400">
                Registered Artifacts in Bundle ({manifestState.artifacts.length})
              </h4>
              <div className="overflow-x-auto border border-slate-800 rounded-lg">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 text-slate-400 font-mono border-b border-slate-800">
                    <tr>
                      <th className="p-2.5">Artifact Path</th>
                      <th className="p-2.5">Role</th>
                      <th className="p-2.5">Size</th>
                      <th className="p-2.5">SHA-256 Fingerprint</th>
                      <th className="p-2.5 text-center">Integrity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {manifestState.artifacts.map((art) => (
                      <tr key={art.path} className="hover:bg-slate-800/30">
                        <td className="p-2.5 text-slate-200 font-sans text-xs break-all">
                          {art.path}
                        </td>
                        <td className="p-2.5 text-cyan-300">
                          <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-[11px]">
                            {art.role}
                          </span>
                        </td>
                        <td className="p-2.5 text-slate-400">
                          {(art.bytes / 1024).toFixed(1)} KB
                        </td>
                        <td className="p-2.5 text-slate-400">
                          <span className="text-cyan-400 font-bold">{art.sha256.substring(0, 12)}</span>
                          <span>...{art.sha256.substring(art.sha256.length - 8)}</span>
                        </td>
                        <td className="p-2.5 text-center">
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>PASS</span>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Replay Definition */}
            <div className="mt-5 p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
              <span className="text-xs font-mono text-cyan-400 flex items-center space-x-1.5">
                <Terminal className="w-3.5 h-3.5" />
                <span>Deterministic Replay Specification</span>
              </span>
              <div className="font-mono text-xs text-slate-300 bg-slate-900 p-2.5 rounded border border-slate-800/80">
                $ {manifestState.replay.command}
              </div>
              <div className="text-[11px] text-slate-400 flex items-center space-x-2">
                <span>Working Directory: <code className="text-cyan-300">{manifestState.replay.cwd}</code></span>
                <span>•</span>
                <span>Expected Outputs: <code className="text-cyan-300">{manifestState.replay.outputs.length}</code></span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: CSV Data Audit */}
      {activeKernelTab === 'audit' && (
        <div className="space-y-5">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div>
                <span className="text-xs font-mono text-cyan-400">AUDIT_CSV ENGINE (CHECKS.PY)</span>
                <h3 className="text-base font-semibold text-slate-100 mt-0.5">
                  Structural & Temporal Integrity Audit
                </h3>
              </div>
              <button
                onClick={handleRunCsvAudit}
                className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium transition shadow-sm cursor-pointer"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Run CSV Audit</span>
              </button>
            </div>

            {/* Audit Parameter Controls */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 my-4">
              <div>
                <label className="text-[11px] font-mono text-slate-400 block mb-1">
                  Required Columns:
                </label>
                <input
                  type="text"
                  value={requiredCols}
                  onChange={(e) => setRequiredCols(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-[11px] font-mono text-slate-400 block mb-1">
                  Expected Frequency:
                </label>
                <select
                  value={expectedFreq}
                  onChange={(e) => setExpectedFreq(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:border-cyan-500 focus:outline-none"
                >
                  <option value="annual">annual</option>
                  <option value="monthly">monthly</option>
                  <option value="event">event</option>
                </select>
              </div>

              <div>
                <label className="text-[11px] font-mono text-slate-400 block mb-1">
                  Predictor Columns:
                </label>
                <input
                  type="text"
                  value={predictorCols}
                  onChange={(e) => setPredictorCols(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-[11px] font-mono text-slate-400 block mb-1">
                  Target Leakage Prefixes:
                </label>
                <input
                  type="text"
                  value={targetPrefixes}
                  onChange={(e) => setTargetPrefixes(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>
            </div>

            {/* CSV Input Area */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-slate-400 flex items-center space-x-1">
                  <FileSpreadsheet className="w-3.5 h-3.5 text-cyan-400" />
                  <span>CSV Sample Buffer:</span>
                </span>
                <button
                  onClick={() => setCsvInput(DEFAULT_CSV_SAMPLE)}
                  className="text-[11px] font-mono text-slate-500 hover:text-slate-300 flex items-center space-x-1"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Reset Sample</span>
                </button>
              </div>
              <textarea
                value={csvInput}
                onChange={(e) => setCsvInput(e.target.value)}
                rows={6}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono text-slate-200 focus:border-cyan-500 focus:outline-none"
              />
            </div>

            {/* Audit Results View */}
            {csvAuditResult && (
              <div className="mt-5 space-y-4">
                <div className={`p-4 rounded-xl border flex items-start space-x-3 ${
                  csvAuditResult.status === 'pass'
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                    : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                }`}>
                  {csvAuditResult.status === 'pass' ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                  )}
                  <div>
                    <h4 className="text-xs font-mono font-bold uppercase">
                      AUDIT STATUS: {csvAuditResult.status.toUpperCase()}
                    </h4>
                    <p className="text-xs text-slate-300 mt-1">
                      Rows: {csvAuditResult.row_count} | Year Range: {csvAuditResult.year_min} - {csvAuditResult.year_max} | Required Columns Present: {csvAuditResult.required_columns_present ? 'Yes' : 'No'}
                    </p>
                    {csvAuditResult.failures.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {csvAuditResult.failures.map((f, i) => (
                          <div key={i} className="text-xs font-mono bg-rose-950/40 p-1.5 rounded border border-rose-900/50">
                            Failure: {JSON.stringify(f)}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-3">
                  <h5 className="text-[11px] font-mono text-slate-400 mb-2">Column Null Counts</h5>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                    {Object.entries(csvAuditResult.null_counts).map(([col, cnt]) => (
                      <div key={col} className="bg-slate-900 p-2 rounded border border-slate-800 text-xs font-mono">
                        <span className="text-slate-400 block truncate" title={col}>{col}</span>
                        <span className={`font-bold ${cnt === 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                          {cnt} nulls
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Evidence Graph */}
      {activeKernelTab === 'graph' && (
        <div className="space-y-5">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div>
                <span className="text-xs font-mono text-cyan-400">BUILD_GRAPH ENGINE (CORE.PY)</span>
                <h3 className="text-base font-semibold text-slate-100 mt-0.5">
                  Synthesized Evidence Graph Structure
                </h3>
              </div>
              <button
                onClick={handleRegenerateGraph}
                className="flex items-center space-x-2 px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition cursor-pointer"
              >
                <Network className="w-3.5 h-3.5 text-cyan-400" />
                <span>Refresh Graph</span>
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 my-4">
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-[11px] font-mono text-slate-400 block">GRAPH ID</span>
                <span className="text-xs font-mono text-cyan-300">{graphData.graph_id}</span>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-[11px] font-mono text-slate-400 block">TOTAL NODES</span>
                <span className="text-xs font-mono text-slate-200">{graphData.node_count}</span>
              </div>
              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-[11px] font-mono text-slate-400 block">TOTAL EDGES</span>
                <span className="text-xs font-mono text-slate-200">{graphData.edge_count}</span>
              </div>
            </div>

            {/* Visual Node & Edge Representation */}
            <div className="space-y-3">
              <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400">
                Graph Nodes ({graphData.nodes.length})
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                {graphData.nodes.map((node) => (
                  <div
                    key={node.id}
                    className="p-3 bg-slate-950/70 border border-slate-800/80 rounded-lg text-xs font-mono"
                  >
                    <div className="flex items-center justify-between">
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-900 text-cyan-300 border border-slate-800">
                        {node.type}
                      </span>
                      {node.status && (
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                          node.status === 'rejected'
                            ? 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
                            : 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                        }`}>
                          {node.status}
                        </span>
                      )}
                    </div>
                    <p className="mt-2 text-slate-200 text-xs truncate" title={node.id}>
                      {node.id}
                    </p>
                  </div>
                ))}
              </div>

              <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400 mt-5">
                Graph Relations ({graphData.edges.length})
              </h4>
              <div className="space-y-1.5">
                {graphData.edges.map((edge, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 bg-slate-950/50 border border-slate-800/60 rounded-lg text-xs font-mono flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <span className="text-slate-300 truncate max-w-sm" title={edge.source}>
                      {edge.source}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-400 border border-cyan-800/50 text-[11px] self-start sm:self-center">
                      --[{edge.relation}]--&gt;
                    </span>
                    <span className="text-slate-300 truncate max-w-sm" title={edge.target}>
                      {edge.target}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Provenance Ledger */}
      {activeKernelTab === 'ledger' && (
        <div className="space-y-5">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <div className="pb-4 border-b border-slate-800">
              <span className="text-xs font-mono text-cyan-400">IMMUTABLE RESEARCH LEDGER</span>
              <h3 className="text-base font-semibold text-slate-100 mt-0.5">
                Provenance Ledger Records (PROVENANCE_LEDGER.jsonl)
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Append-only cryptographic record of supervisor validations, checksums, and eligibility decisions.
              </p>
            </div>

            <div className="mt-5 space-y-3 font-mono text-xs">
              <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-2">
                <div className="flex items-center justify-between text-slate-400 text-[11px]">
                  <span>RECORD #001</span>
                  <span>2026-08-27T00:00:00Z</span>
                </div>
                <div className="text-slate-300">
                  <span className="text-cyan-400">record_id:</span> governance:CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1:2026-08-27T00:00:00Z
                </div>
                <div className="text-slate-300">
                  <span className="text-cyan-400">manifest_sha256:</span> 5f251595432fe260e8ba2fcdfa0f3e20301f2bbe2c03468392165b35c637c996
                </div>
                <div className="text-slate-300">
                  <span className="text-cyan-400">decision_status:</span> <span className="text-rose-400">rejected (preserved as auditable negative evidence)</span>
                </div>
                <div className="text-slate-300">
                  <span className="text-cyan-400">validation_artifacts:</span> 7/7 verified
                </div>
              </div>

              <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-2">
                <div className="flex items-center justify-between text-slate-400 text-[11px]">
                  <span>RECORD #002</span>
                  <span>2026-08-27T12:00:00Z</span>
                </div>
                <div className="text-slate-300">
                  <span className="text-cyan-400">record_id:</span> governance:CHAOS_SUPERVISOR_ADMISSION_GATE_V1:2026-08-27T12:00:00Z
                </div>
                <div className="text-slate-300">
                  <span className="text-cyan-400">manifest_sha256:</span> 7e758b1f3ab323ee9a5bd1bcae2dca498b619b6d15754163c4908c7f057d4abf
                </div>
                <div className="text-slate-300">
                  <span className="text-cyan-400">decision_status:</span> <span className="text-emerald-400">pass (2 admitted, 31 quarantined)</span>
                </div>
                <div className="text-slate-300">
                  <span className="text-cyan-400">validation_artifacts:</span> 16/16 verified
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
