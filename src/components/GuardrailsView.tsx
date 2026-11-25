import React from 'react';
import { AlertTriangle, BookOpen, GitCommit, ArrowRight, ShieldCheck } from 'lucide-react';

export const GuardrailsView: React.FC = () => {
  const guardrails = [
    {
      title: "1. No Forced Source Reconciliation",
      description: "Do not artificially force divergent indicators (e.g. World Bank GDP vs IMF WEO GDP vs national accounts) into a single hybrid value. Discrepancies represent real measurement and conceptual divergence."
    },
    {
      title: "2. No Blanket Imputation",
      description: "Never fill missing panel cells with linear interpolations, forward fills, or mean imputations. Missing data remains explicitly null, and algorithms must either handle sparsity natively or entities are partitioned out."
    },
    {
      title: "3. No Frequency Distortion Without Alignment Contracts",
      description: "Never downsample daily/event data to annual aggregates (or upsample annual to monthly) without an explicitly registered, mathematically auditable alignment contract."
    },
    {
      title: "4. Temporal Precedence Guardrail",
      description: "Future outcomes can never be retrofitted to define current or past state classifications. State panels must only consume historical evidence strictly available at timestamp t."
    },
    {
      title: "5. Auditable Negative Evidence",
      description: "Null results, failed hypothesis tests, and rejected predictive attempts are never deleted, suppressed, or rewritten. They are preserved in the permanent provenance ledger with zero composer weight."
    },
    {
      title: "6. Permutation Nulls & Max-Stat Required",
      description: "Any edge candidate must outperform family-wise maximum statistic null distributions to guard against false discoveries arising from wide algorithmic search spaces."
    },
    {
      title: "7. Zero Causal Claims Permitted",
      description: "Observational correlations, predictive transfer gains, and out-of-sample improvements remain strictly predictive associations. No causal claims are admitted into the governance ledger."
    }
  ];

  const ontologyLevels = [
    { name: "Domain", desc: "Autonomous source boundary (Trade, Energy, Institutions, Macro)" },
    { name: "State", desc: "Observable condition at timestamp t based strictly on backward-looking data" },
    { name: "Edge", desc: "Direct temporal transition or predictive link between two states" },
    { name: "Path", desc: "Composite sequence of admitted edges across or within domains" },
    { name: "Pattern", desc: "Empirically validated structural recurrence supported by out-of-sample tests" },
    { name: "Runtime", desc: "Immutable reference snapshot strictly decoupled from live execution" }
  ];

  return (
    <div className="space-y-6">
      {/* Header Summary */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <div className="flex items-center space-x-2 text-amber-400 mb-1">
          <AlertTriangle className="w-5 h-5" />
          <h2 className="text-base font-bold text-slate-100">Scientific Guardrails & Epistemic Framework</h2>
        </div>
        <p className="text-xs text-slate-400 mt-1">
          Governing principles preventing common statistical pitfalls, false discoveries, and data leakage across multi-domain research.
        </p>
      </div>

      {/* Ontological Progression */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-base font-semibold text-slate-100 flex items-center space-x-2 mb-3">
          <BookOpen className="w-4 h-4 text-cyan-400" />
          <span>CHAOS Ontological Hierarchy</span>
        </h3>
        <p className="text-xs text-slate-400 mb-4">
          Hierarchical abstraction levels governing evidence progression from raw source domains to runtime reference:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2">
          {ontologyLevels.map((lvl, idx) => (
            <div
              key={lvl.name}
              className="bg-slate-950 p-3 rounded-lg border border-slate-800 relative flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between text-xs font-mono text-cyan-400 mb-1">
                  <span>LEVEL {idx + 1}</span>
                  {idx < ontologyLevels.length - 1 && (
                    <ArrowRight className="w-3 h-3 text-slate-600 hidden lg:block" />
                  )}
                </div>
                <h4 className="text-sm font-bold text-slate-100">{lvl.name}</h4>
                <p className="text-[11px] text-slate-400 mt-1 leading-snug">{lvl.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* The 7 Invariant Rules */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-base font-semibold text-slate-100 flex items-center space-x-2 mb-4">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Core Invariant Research Guardrails</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {guardrails.map((g, i) => (
            <div
              key={i}
              className="p-4 bg-slate-950/60 border border-slate-800/80 rounded-xl space-y-1.5"
            >
              <h4 className="text-xs font-bold font-mono text-cyan-300 flex items-center space-x-1.5">
                <span>{g.title}</span>
              </h4>
              <p className="text-xs text-slate-300 leading-relaxed">
                {g.description}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Immutable Reference Snapshot */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-base font-semibold text-slate-100 flex items-center space-x-2 mb-2">
          <GitCommit className="w-4 h-4 text-cyan-400" />
          <span>Immutable Reference Snapshot Anchoring</span>
        </h3>
        <p className="text-xs text-slate-400 mb-3">
          All experimental runs anchor to immutable snapshot hashes to guarantee strict reproducibility:
        </p>

        <div className="font-mono text-xs bg-slate-950 p-4 rounded-lg border border-slate-800 space-y-1.5 text-slate-300">
          <div><span className="text-cyan-400">parent_research_snapshot:</span> experiments/macro_plus_eia_energy/RESEARCH_SNAPSHOT_V3.json</div>
          <div><span className="text-cyan-400">parent_commit:</span> 4a1a75fe553c9595a1fac9cde60f735cd0700509</div>
          <div><span className="text-cyan-400">campaign_id:</span> CHAOS_OPEN_MULTI_DOMAIN_CAMPAIGN_V1</div>
          <div><span className="text-cyan-400">governance_mode:</span> deterministic_audit_ledger</div>
        </div>
      </div>
    </div>
  );
};
