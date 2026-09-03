import {
  SupervisorGateDecision,
  AgentSpec,
  ExperimentalContractSummary,
  GovernanceBundle,
  ModelBenchmarkResult,
  EvidenceGraphData
} from '../types';

export const SUPERVISOR_GATE_DATA: SupervisorGateDecision = {
  gate_id: "CHAOS_SUPERVISOR_ADMISSION_GATE_V1",
  input_files: 16,
  admitted_supported_predictive_records: 2,
  quarantined_records: 31,
  positive_composition_statuses: ["supported_predictive"],
  causal_claims_admitted: 0,
  missing_or_failed_inputs: 0,
  input_hashes: {
    "experiments/macro_plus_eia_energy/transition_evidence_v1/TRANSITION_EVIDENCE_V1.jsonl": "7e758b1f3ab323ee9a5bd1bcae2dca498b619b6d15754163c4908c7f057d4abf",
    "experiments/multi_domain_native_adapters_v1/TRANSITION_EVIDENCE_NATIVE_DOMAINS_V1.jsonl": "21b2d619ff31cc71705613140fda5e9faa582fbe1ec39ff4e6d76354722c8f34",
    "experiments/multi_domain_native_edges_v1/TRANSITION_EVIDENCE_ECONOMIC_TO_CONFLICT_V1.jsonl": "079f739ead4bdbe9e18c3641f7728962cc2c3196a2bc3bf728adcdaf40bb1620",
    "campaigns/agents/trade_v1/TRADE_TRANSITION_EVIDENCE_V1.jsonl": "f2b97903d37dd349587fe63d88c77812040a0be7fde76b1962ce25b4156c19ca",
    "campaigns/agents/trade_v1/WDI_TRADE_TRANSITION_EVIDENCE_V1.jsonl": "1945b9f3ef1392548ca9643e423cd99c220d8513815ae81048d152eea16177d3",
    "campaigns/agents/trade_v1/WDI_TRADE_TO_ECONOMIC_DETERIORATION_TRANSITION_EVIDENCE_V1.jsonl": "25299da644f7dc9a201e5c5d61de29fee28f89d115f812fbd46e8ea0726557fd",
    "campaigns/agents/institutions_policy_v1/WGI_TRANSITION_EVIDENCE_V1.jsonl": "9d3f4070893c5c7ab8f62991fb35f7e45a1f31b9feb405504186ba2f7d4787de",
    "campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/OECD_PMR_TRANSITION_EVIDENCE_V1.jsonl": "6de52d41f8196baa2bd5a5428d4a4eda5e3763c713c28cb3f54b35293a34cd75",
    "experiments/multi_domain_native_edges_v1/pmr_within_domain_v1/PMR_WITHIN_DOMAIN_TRANSITION_EVIDENCE_V1_1.jsonl": "7c28f75aa683e4654f617e878cf1a1b46abce681d1356fc684107017c8dd3329",
    "experiments/multi_domain_native_edges_v1/imf_imts_export_to_gdp_v1/IMF_IMTS_EXPORT_TO_GDP_TRANSITION_EVIDENCE_V1.jsonl": "bf11dcb2f89dfab736e42329b77e25c5c5f1e989012637c7849bdab6f28c212e",
    "experiments/multi_domain_native_edges_v1/imf_partner_dependence_v1/IMF_IMTS_PARTNER_DEPENDENCE_TRANSITION_EVIDENCE_V1.jsonl": "56d1c7844ce005701e5eea5fa2097c1292c21432ae41394aaac0a5b660004bf2",
    "experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_DEPENDENCE_TRANSITION_EVIDENCE_V2.jsonl": "17dc127e0e6d6dc942d45999ab4aa3d410e85e3a712323b599f2df6f749195e3",
    "experiments/dual_track_v02/imf_partner_substitution_v3/IMF_IMTS_PARTNER_SUBSTITUTION_TRANSITION_EVIDENCE_V3.jsonl": "5c29ba97a079b02f0ad9839cd85575079f1589cf9ae7dacf2acac3ece9f12a6e",
    "experiments/dual_track_v02/imf_partner_substitution_v3_1/IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_TRANSITION_EVIDENCE.jsonl": "638d17aafb672f0397f6dcb9d74144184db936aaf06b7485986cdb9f07639e38",
    "experiments/dual_track_v02/trade_network_adaptation_path_v1_1/TRADE_NETWORK_ADAPTATION_PATH_TRANSITION_EVIDENCE_V1_1.jsonl": "652c40187ea08a950abf40478100f33babd54630292752909c8ab72ce0b110b8",
    "experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_TRANSITION_EVIDENCE_V1.jsonl": "c1850ac59b0f53c9d76c8cd642bfb7902924352239dbbaa4481054fbb6ec6ad9"
  },
  rules: {
    rejected_positive_weight: false,
    unresolved_positive_weight: false,
    not_testable_positive_weight: false,
    provisional_descriptive_positive_weight: false,
    future_outcome_current_state: false
  },
  status: 'pass'
};

export const AGENT_SPECS: AgentSpec[] = [
  {
    agent_id: "TRADE_AGENT_V1",
    domain: "trade",
    priority: 1,
    scope: "UN Comtrade or source-native trade assets already available; no bulk download without source contract",
    workspace: "campaigns/agents/trade_v1/",
    outputs: ["ObservedRecord", "DomainState", "TransitionEvidence", "provenance_manifest", "run_manifest"],
    allowed_statuses: ["candidate", "supported_predictive", "rejected", "unresolved", "not_testable"],
    shared_write: "supervisor_review_only",
    last_run_status: "synced"
  },
  {
    agent_id: "INSTITUTIONS_POLICY_AGENT_V1",
    domain: "institutions_policy",
    priority: 1,
    scope: "Source-defined dated institutional and policy observations; separate continuity, transition, policy shock, and leader-specific deviation",
    workspace: "campaigns/agents/institutions_policy_v1/",
    outputs: ["ObservedRecord", "DomainState", "TransitionEvidence", "provenance_manifest", "run_manifest"],
    allowed_statuses: ["candidate", "supported_predictive", "rejected", "unresolved", "not_testable"],
    shared_write: "supervisor_review_only",
    last_run_status: "synced"
  },
  {
    agent_id: "ENERGY_AGENT_V1",
    domain: "energy",
    priority: 2,
    scope: "Existing EIA annual series and source-native energy states; re-test within-domain edges without reusing rejected mediator as success",
    workspace: "campaigns/agents/energy_v1/",
    outputs: ["DomainState", "TransitionEvidence", "run_manifest"],
    allowed_statuses: ["candidate", "supported_predictive", "rejected", "unresolved", "not_testable"],
    shared_write: "supervisor_review_only",
    last_run_status: "active"
  },
  {
    agent_id: "ENVIRONMENT_DISASTER_AGENT_V1",
    domain: "environment_disaster",
    priority: 2,
    scope: "USGS/NOAA event or native-frequency assets; Event -> Production Shock -> Recovery only with explicit alignment contract",
    workspace: "campaigns/agents/environment_disaster_v1/",
    outputs: ["ObservedRecord", "DomainState", "TransitionEvidence", "provenance_manifest", "run_manifest"],
    allowed_statuses: ["candidate", "supported_predictive", "rejected", "unresolved", "not_testable"],
    shared_write: "supervisor_review_only",
    last_run_status: "quarantined"
  },
  {
    agent_id: "HEALTH_PANDEMIC_AGENT_V1",
    domain: "health_pandemic",
    priority: 2,
    scope: "WHO/authoritative health event or daily/monthly assets; strictly no annual pandemic dummy",
    workspace: "campaigns/agents/health_pandemic_v1/",
    outputs: ["ObservedRecord", "DomainState", "TransitionEvidence", "provenance_manifest", "run_manifest"],
    allowed_statuses: ["candidate", "supported_predictive", "rejected", "unresolved", "not_testable"],
    shared_write: "supervisor_review_only",
    last_run_status: "quarantined"
  },
  {
    agent_id: "EVIDENCE_COMPOSITION_AGENT_V1",
    domain: "cross_domain",
    priority: 3,
    scope: "Supervisor-gated graph and path assembly only after per-domain edges pass eligibility",
    workspace: "campaigns/agents/evidence_composition_v1/",
    outputs: ["EvidenceGraph", "PathCandidate", "EligibilityDecision", "run_manifest"],
    allowed_statuses: ["candidate", "supported_predictive", "rejected", "unresolved", "not_testable"],
    shared_write: "supervisor_only",
    last_run_status: "active"
  }
];

export const EXPERIMENTAL_CONTRACTS: ExperimentalContractSummary[] = [
  {
    id: "CONTRACT_MACRO_PLUS_EIA_ENERGY_V1_1",
    title: "Macro Plus EIA Energy Panel Contract",
    domain: "Macro-Energy Nexus",
    status: "review_only",
    version: "1.1 (Annual 2000-2024)",
    frequency: "Annual",
    timeframe: "2000 - 2024 (25 Years)",
    description: "Strict review-only contract covering 139 complete numeric entities and 11 source-separated indicators from World Bank WDI, IMF WEO, and EIA.",
    authorized_variables: [
      { name: "GDP per capita (constant 2015 US$)", source: "World Bank WDI", code: "NY.GDP.PCAP.KD" },
      { name: "GDP growth (annual %)", source: "World Bank WDI", code: "NY.GDP.MKTP.KD.ZG" },
      { name: "Inflation, consumer prices (annual %)", source: "World Bank WDI", code: "FP.CPI.TOTL.ZG" },
      { name: "Exports of goods & services (% of GDP)", source: "World Bank WDI", code: "NE.EXP.GNFS.ZS" },
      { name: "Imports of goods & services (% of GDP)", source: "World Bank WDI", code: "NE.IMP.GNFS.ZS" },
      { name: "General gov gross debt (% of GDP)", source: "IMF WEO", code: "GGXWDG_NGDP" },
      { name: "Current account balance (% of GDP)", source: "IMF WEO", code: "BCA_NGDPD" },
      { name: "Total Primary Energy Consumption", source: "US EIA", code: "TOTAL_CONS_QUAD_BTU" },
      { name: "Total Primary Energy Production", source: "US EIA", code: "TOTAL_PROD_QUAD_BTU" },
      { name: "CO2 Emissions from Fuel Combustion", source: "US EIA", code: "CO2_EMISSIONS_MMT" },
      { name: "Net Energy Import Share", source: "Derived EIA", code: "NET_ENERGY_IMPORT_RATIO" }
    ],
    guardrails: [
      "No blanket imputation: missing cells remain null in raw storage",
      "No synthetic frequency upsampling from annual to quarterly",
      "Strict chronological out-of-sample partition (Train: 2000-2016, Val: 2017-2019, Test: 2020-2024)",
      "Zero causal claims permitted: predictive associations only"
    ],
    hypothesis: "Tests whether lagged energy balance deviations predict macro deterioration with greater lead-time accuracy than autoregressive univariate history."
  },
  {
    id: "IMF_IMTS_PARTNER_DEPENDENCE_CONTRACT_V2",
    title: "IMF IMTS Dominant Partner Substitution Contract",
    domain: "International Trade",
    status: "quarantined",
    version: "2.0 (Auditable Negative Evidence)",
    frequency: "Annual",
    timeframe: "2000 - 2024",
    description: "Evaluates whether concentrated bilateral export exposures trigger regime shifts when top trading partner demand contracts.",
    authorized_variables: [
      { name: "Top Partner Export Concentration", source: "IMF IMTS", code: "IMTS_TOP1_SHARE" },
      { name: "Bilateral Trade Contraction Rate", source: "IMF IMTS", code: "IMTS_TOP1_GROWTH" },
      { name: "Secondary Partner Absorption Buffer", source: "IMF IMTS", code: "IMTS_BUFFER_RATIO" }
    ],
    guardrails: [
      "Preserved as auditable negative evidence after max-stat permutation tests failed null rejection",
      "No positive composer weight granted in supervisor gate",
      "Zero survivor bias: unrepresented developing economies flagged"
    ],
    hypothesis: "Hypothesized that single-partner export reliance >40% accelerates GDP contraction during global downturns. Result: Null hypothesis could not be rejected."
  },
  {
    id: "WGI_INSTITUTIONAL_EDGE_CONTRACT_V1",
    title: "Worldwide Governance Indicators Edge Contract",
    domain: "Institutions & Policy",
    status: "review_only",
    version: "1.0",
    frequency: "Annual",
    timeframe: "2002 - 2024",
    description: "Defines state representations for institutional effectiveness and regulatory quality without conflating gradual institutional drift with acute policy shocks.",
    authorized_variables: [
      { name: "Voice & Accountability", source: "World Bank WGI", code: "WGI_VA" },
      { name: "Political Stability & No Violence", source: "World Bank WGI", code: "WGI_PV" },
      { name: "Government Effectiveness", source: "World Bank WGI", code: "WGI_GE" },
      { name: "Regulatory Quality", source: "World Bank WGI", code: "WGI_RQ" },
      { name: "Rule of Law", source: "World Bank WGI", code: "WGI_RL" },
      { name: "Control of Corruption", source: "World Bank WGI", code: "WGI_CC" }
    ],
    guardrails: [
      "Separates structural baseline levels from discrete policy reforms",
      "Disallows contemporaneous outcome variable usage in indicator definitions"
    ],
    hypothesis: "Tests if multi-year institutional deteriorations act as asymmetric risk amplifiers during external macro shocks."
  },
  {
    id: "REGIME_LOCKED_TEST_CONTRACT_V1",
    title: "Regime Locked Out-of-Sample Test Contract",
    domain: "Systemic Macro",
    status: "frozen",
    version: "1.0 (Immutable Reference)",
    frequency: "Annual",
    timeframe: "2020 - 2024 Locked Split",
    description: "Completely frozen test partition guarding against data leakage and iterative parameter tuning on pandemic and post-pandemic cycles.",
    authorized_variables: [
      { name: "Target Variable: Real GDP Growth", source: "WDI", code: "NY.GDP.MKTP.KD.ZG" },
      { name: "Exogenous Predictor Panel", source: "Multi-Source", code: "MACRO_ENERGY_11" }
    ],
    guardrails: [
      "Checkpoint hashes locked and verified against Git tree",
      "No re-training or threshold adaptation permitted on test split"
    ],
    hypothesis: "Evaluates whether Temporal Fusion Transformer maintains predictive superiority against simple mean baselines in high-volatility holdout years."
  }
];

export const SAMPLE_GOVERNANCE_BUNDLE: GovernanceBundle = {
  bundle_id: "CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1",
  decision_status: "quarantined",
  artifacts: [
    {
      path: "experimental_contracts/dual_track_v02/TRADE_REGIME_TRANSITION_DISCOVERY_CONTRACT_V1.json",
      role: "contract",
      sha256: "3d64c727feffc9bd46df4c9790fb79698898c341a5347fd81060b41f1618f0d5",
      bytes: 7100,
      verified: true
    },
    {
      path: "campaigns/dual_track_v02/CHAOS_DUAL_TRACK_PROTOCOL_V0_2.json",
      role: "protocol",
      sha256: "f2eb1e89f1539362b8166603b24271105251eb401455c1a0868f5bd183a2e053",
      bytes: 6750,
      verified: true
    },
    {
      path: "experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_STATE_PANEL_V1.csv",
      role: "state_panel",
      sha256: "c35cd7232fb3c64071d19164c73fd5987d63fbf7ab9db3a86e19bd072953e588",
      bytes: 423964,
      verified: true
    },
    {
      path: "experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_EVENTS_V1.csv",
      role: "events",
      sha256: "db7c93780370138779f7772c3965c5a1d1c3e85ea793aae4ab1f6bed7b305a22",
      bytes: 16667,
      verified: true
    },
    {
      path: "experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_ROLLING_METRICS_V1.csv",
      role: "rolling_metrics",
      sha256: "7f1e657554298bdd2d8412e83b5ab9197c42a3765b3c0160f7be0446d3749fe3",
      bytes: 1481,
      verified: true
    },
    {
      path: "experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_NULL_SUMMARIES_V1.json",
      role: "null_summaries",
      sha256: "080b19bce5d2e5bdf6d98ea985d157d682fe236831a5a676493c71b354473099",
      bytes: 910,
      verified: true
    },
    {
      path: "experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_TRANSITION_EVIDENCE_V1.jsonl",
      role: "transition_evidence",
      sha256: "c1850ac59b0f53c9d76c8cd642bfb7902924352239dbbaa4481054fbb6ec6ad9",
      bytes: 3999,
      verified: true
    }
  ],
  replay: {
    command: "python3 tooling/build_trade_regime_transition_transition_evidence_v1.py",
    cwd: ".",
    outputs: [
      {
        path: "experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_TRANSITION_EVIDENCE_V1.jsonl",
        sha256: "c1850ac59b0f53c9d76c8cd642bfb7902924352239dbbaa4481054fbb6ec6ad9"
      }
    ]
  },
  decision: {
    rule: "contractual_admission_gate",
    status: "rejected",
    notes: "Final predictive trade-regime attempt failed contractual admission criteria; preserved as auditable negative evidence."
  }
};

export const MODEL_BENCHMARKS: ModelBenchmarkResult[] = [
  {
    model_id: "TFT_V1_1_BEST",
    name: "Temporal Fusion Transformer (TFT)",
    encoder_steps: 5,
    seed: 17,
    val_loss: 1.5502,
    test_mae: 3.9360,
    p10_loss: 0.884,
    p50_loss: 3.039,
    p90_loss: 7.882,
    epoch: 16,
    status: "converged",
    notes: "+3.24% MAE improvement over global train mean; 77.4% directional accuracy"
  },
  {
    model_id: "BASELINE_GLOBAL_MEAN",
    name: "Global Train Mean Baseline",
    encoder_steps: 0,
    seed: 0,
    val_loss: 1.8940,
    test_mae: 4.0679,
    p10_loss: 0.941,
    p50_loss: 3.190,
    p90_loss: 8.072,
    epoch: 0,
    status: "baseline",
    notes: "Unconditional target mean estimator"
  },
  {
    model_id: "BASELINE_ENTITY_MEAN",
    name: "Entity Train Mean Baseline",
    encoder_steps: 0,
    seed: 0,
    val_loss: 1.9420,
    test_mae: 4.2962,
    p10_loss: 1.050,
    p50_loss: 3.380,
    p90_loss: 8.420,
    epoch: 0,
    status: "baseline",
    notes: "Entity-specific historical target mean estimator"
  },
  {
    model_id: "BASELINE_PERSISTENCE",
    name: "One-Step Persistence (Lag-1)",
    encoder_steps: 1,
    seed: 0,
    val_loss: 2.1105,
    test_mae: 4.5420,
    p10_loss: 1.120,
    p50_loss: 3.650,
    p90_loss: 8.910,
    epoch: 0,
    status: "baseline",
    notes: "Carry forward previous observed year value"
  },
  {
    model_id: "ABLATION_WDI_ONLY",
    name: "TFT Ablation: WDI Macro Only",
    encoder_steps: 5,
    seed: 17,
    val_loss: 1.5502,
    test_mae: 3.9480,
    p10_loss: 0.892,
    p50_loss: 3.055,
    p90_loss: 7.910,
    epoch: 16,
    status: "ablation",
    notes: "Excludes EIA energy & IMF fiscal features"
  },
  {
    model_id: "ABLATION_IMF_ONLY",
    name: "TFT Ablation: IMF Fiscal Only",
    encoder_steps: 5,
    seed: 17,
    val_loss: 1.5910,
    test_mae: 4.0150,
    p10_loss: 0.920,
    p50_loss: 3.120,
    p90_loss: 8.010,
    epoch: 19,
    status: "ablation",
    notes: "Fiscal deficit and debt indicators only"
  },
  {
    model_id: "ABLATION_EIA_ONLY",
    name: "TFT Ablation: EIA Energy Only",
    encoder_steps: 5,
    seed: 17,
    val_loss: 1.6038,
    test_mae: 4.1120,
    p10_loss: 0.950,
    p50_loss: 3.230,
    p90_loss: 8.160,
    epoch: 13,
    status: "ablation",
    notes: "Energy production, consumption, and CO2 series only"
  }
];

export const VARIABLE_IMPORTANCE_RANKINGS = [
  { variable: "GDP Growth (t-1)", source: "WDI", importance: 0.285, category: "autoregressive" },
  { variable: "Energy Consumption per Capita", source: "EIA/WDI", importance: 0.178, category: "energy" },
  { variable: "Net Energy Import Ratio", source: "EIA", importance: 0.142, category: "energy" },
  { variable: "Inflation CPI YoY", source: "WDI", importance: 0.121, category: "macro" },
  { variable: "General Gov Debt (% of GDP)", source: "IMF", importance: 0.098, category: "fiscal" },
  { variable: "Trade Openness (Exports+Imports)", source: "WDI", importance: 0.076, category: "trade" },
  { variable: "Current Account Balance (% of GDP)", source: "IMF", importance: 0.062, category: "external" },
  { variable: "CO2 Emissions Volume", source: "EIA", importance: 0.038, category: "energy" }
];

export const DATA_READINESS_METRICS = {
  gate_status: "DATA_READINESS_GATE_ONLY",
  raw_entities_universe: 264,
  imf_weo_entities: 197,
  intersection_entities: 194,
  strict_complete_raw_wide: 140,
  strict_complete_numeric: 139,
  sample_years: 25,
  period: "2000 - 2024",
  total_cells_audited: 97000,
  nonempty_cells: 87728,
  missing_cells_preserved_null: 9272,
  imputation_applied: false,
  source_reconciliation_forced: false,
  breakdown: [
    { stage: "All Tracked Entities (WDI)", count: 264, pct: 100 },
    { stage: "WDI & IMF Identifier Intersection", count: 194, pct: 73.5 },
    { stage: "Raw Multi-Variable Complete (11 Vars)", count: 140, pct: 53.0 },
    { stage: "Strict Numeric Clean Complete", count: 139, pct: 52.7 }
  ]
};

export const INITIAL_EVIDENCE_GRAPH: EvidenceGraphData = {
  graph_id: "graph:CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1",
  generated_at: "2026-08-27T00:00:00Z",
  nodes: [
    { id: "CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", type: "governance_bundle", status: "rejected" },
    { id: "artifact:experimental_contracts/dual_track_v02/TRADE_REGIME_TRANSITION_DISCOVERY_CONTRACT_V1.json", type: "contract" },
    { id: "artifact:campaigns/dual_track_v02/CHAOS_DUAL_TRACK_PROTOCOL_V0_2.json", type: "protocol" },
    { id: "artifact:experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_STATE_PANEL_V1.csv", type: "state_panel" },
    { id: "artifact:experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_EVENTS_V1.csv", type: "events" },
    { id: "artifact:experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_ROLLING_METRICS_V1.csv", type: "rolling_metrics" },
    { id: "artifact:experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_TRANSITION_EVIDENCE_V1.jsonl", type: "transition_evidence" },
    { id: "replay:CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", type: "replay_run", status: "declared" },
    { id: "decision:CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", type: "decision", status: "rejected" }
  ],
  edges: [
    { source: "artifact:experimental_contracts/dual_track_v02/TRADE_REGIME_TRANSITION_DISCOVERY_CONTRACT_V1.json", target: "CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", relation: "is_registered_in" },
    { source: "artifact:campaigns/dual_track_v02/CHAOS_DUAL_TRACK_PROTOCOL_V0_2.json", target: "CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", relation: "is_registered_in" },
    { source: "artifact:experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_STATE_PANEL_V1.csv", target: "CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", relation: "is_registered_in" },
    { source: "artifact:experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_EVENTS_V1.csv", target: "CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", relation: "is_registered_in" },
    { source: "CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", target: "replay:CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", relation: "has_replay" },
    { source: "replay:CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", target: "artifact:experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_TRANSITION_EVIDENCE_V1.jsonl", relation: "produces" },
    { source: "CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", target: "decision:CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1", relation: "supports_decision" }
  ],
  node_count: 9,
  edge_count: 7
};
