export interface SupervisorGateDecision {
  gate_id: string;
  input_files: number;
  admitted_supported_predictive_records: number;
  quarantined_records: number;
  positive_composition_statuses: string[];
  causal_claims_admitted: number;
  missing_or_failed_inputs: number;
  input_hashes: Record<string, string>;
  rules: {
    rejected_positive_weight: boolean;
    unresolved_positive_weight: boolean;
    not_testable_positive_weight: boolean;
    provisional_descriptive_positive_weight: boolean;
    future_outcome_current_state: boolean;
  };
  status: 'pass' | 'fail' | 'blocked';
}

export interface AgentSpec {
  agent_id: string;
  domain: string;
  priority: number;
  scope: string;
  workspace: string;
  outputs: string[];
  allowed_statuses: string[];
  shared_write: string;
  last_run_status?: 'active' | 'synced' | 'quarantined' | 'completed';
}

export interface ExperimentalContractSummary {
  id: string;
  title: string;
  domain: string;
  status: 'review_only' | 'admitted' | 'quarantined' | 'in_progress' | 'frozen';
  version: string;
  frequency: string;
  timeframe: string;
  description: string;
  authorized_variables: Array<{ name: string; source: string; code: string }>;
  guardrails: string[];
  hypothesis: string;
}

export interface GovernanceArtifact {
  path: string;
  role: string;
  sha256: string;
  bytes: number;
  verified?: boolean;
}

export interface GovernanceBundle {
  bundle_id: string;
  decision_status: 'admitted' | 'quarantined' | 'review_required' | 'provisional';
  artifacts: GovernanceArtifact[];
  replay: {
    command: string;
    cwd: string;
    outputs: Array<{ path: string; sha256: string }>;
  };
  decision: {
    rule: string;
    status: string;
    notes: string;
  };
}

export interface EvidenceGraphNode {
  id: string;
  type: string;
  status?: string;
  sha256?: string;
  bytes?: number;
}

export interface EvidenceGraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface EvidenceGraphData {
  graph_id: string;
  generated_at: string;
  nodes: EvidenceGraphNode[];
  edges: EvidenceGraphEdge[];
  node_count: number;
  edge_count: number;
}

export interface CSVDataAuditSummary {
  path: string;
  columns: string[];
  row_count: number;
  year_min: number | null;
  year_max: number | null;
  null_counts: Record<string, number>;
  required_columns_present: boolean;
  expected_frequency: string;
  status: 'pass' | 'fail';
  failures: Array<{ reason: string; [key: string]: unknown }>;
}

export interface ModelBenchmarkResult {
  model_id: string;
  name: string;
  encoder_steps: number;
  seed: number;
  val_loss: number;
  test_mae: number;
  p10_loss: number;
  p50_loss: number;
  p90_loss: number;
  epoch: number;
  status: 'converged' | 'baseline' | 'ablation';
  notes: string;
}

export interface StressTestSplitResult {
  splitId: string;
  label: string;
  trainAccuracy?: number;
  testAccuracy: number;
  directionalAccuracy?: number;
  zScore: number;
  pValue: number;
  status: 'PASSED_OOS' | 'PARTIAL_RESILIENCE' | 'FAILED';
  note?: string;
}

export interface InvariantStressTestReport {
  candidateId: string;
  name: string;
  mathematical_form: string;
  windows_tested: number;
  windows_passed: number;
  average_oos_accuracy: number;
  composite_z_score: string;
  bonferroni_p_value: number;
  lambda_plateau: string;
  peak_lambda: number;
  status: 'ADMITTED_RESILIENT_INVARIANT' | 'PARTIAL_RESILIENT_SURVIVOR' | 'DISQUALIFIED';
  splits: StressTestSplitResult[];
  diagnostic_notes: string;
  structural_family: string;
}

export interface CandidateInvariant {
  id: string;
  name: string;
  mathematical_form: string;
  domains: string[];
  sample_size: number;
  contraction_ratio_lambda: number;
  p_value_null_model: number;
  z_score: number;
  test_accuracy: number;
  status: 'admitted_candidate' | 'quarantined' | 'evaluating';
  rejection_reason?: string;
  evidence_anchor: string;
  discovered_at: string;
  parameters: Record<string, number | string>;
  stress_test?: InvariantStressTestReport;
}

export interface DiscoveryRunMetrics {
  total_candidates_generated: number;
  pruned_early: number;
  evaluated_against_null: number;
  quarantined_count: number;
  admitted_candidates_count: number;
  candidates_per_second: number;
  duration_ms: number;
  active_domains: string[];
}

// CHAOS V1 Real Runtime Types
export interface RuntimeEventInput {
  id: string;
  timestamp: string; // ISO date string or YYYY-MM-DD
  domain: 'seismic' | 'energy' | 'macro' | 'conflict' | 'general';
  magnitude: number; // 0 to 10 scale (e.g. M5.8 or price shock index 0-100 normalized)
  locationOrAsset: string;
  notes?: string;
  usgsId?: string; // Official USGS Event ID (e.g. us7000tcf3)
  coordinates?: [number, number]; // [lat, lon]
  usgsUrl?: string; // Direct link to earthquake.usgs.gov
  isVerifiedUsgs?: boolean; // Certified official catalog record
}

export interface InvariantPatternMatch {
  patternType: 'LPPLS_LOG_PERIODIC' | 'SCALE_CONTRACTION' | 'CROSS_DOMAIN_LAG';
  confidence: number; // percentage (e.g. 89.2)
  estimatedTc: string; // Critical transition date/horizon
  contractionRatio: number; // e.g. 0.618
  zScore: number;
  fittedIntervals: {
    index: number;
    deltaDaysObserved: number;
    deltaDaysFitted: number;
    ratio: number;
  }[];
  description: string;
}

export interface CrossDomainCouplingAnalysis {
  leadDomain: string;
  lagDomain: string;
  measuredLagDays: number;
  couplingCoefficient: number; // 0 to 1
  energyTransferPValue: number;
  causalFlowDirection: string;
  transferDetails: string;
}

export interface RuntimeForecastWindow {
  windowId: string;
  horizonName: string;
  projectedDate: string;
  confidenceIntervalDays: [string, string]; // [earliest, latest]
  predictedMagnitudeRange: [number, number];
  singularityRiskScore: number; // 0-100%
  underlyingInvariantFormula: string;
  recommendedGovernanceAction: string;
}

export interface ChaosRuntimeExecutionResult {
  v1Version: string;
  timestamp: string;
  totalEventsProcessed: number;
  eventsDomainBreakdown: Record<string, number>;
  invariantModelUsed: {
    id: string;
    formula: string;
    peakLambda: number;
    oosAccuracy: number;
    zScore: string;
  };
  patternMatches: InvariantPatternMatch[];
  crossDomainCouplings: CrossDomainCouplingAnalysis[];
  forecasts: RuntimeForecastWindow[];
  filtersApplied: {
    minMagnitudeThreshold: number;
    significanceConfidence: number;
    outlierScrubbing: boolean;
  };
}

export interface StandardTimeSeriesPoint {
  date: string;
  timestamp: number; // Unix timestamp ms
  value: number;
}

export interface StandardTimeSeries {
  id: string;
  name: string;
  source: string;
  indicatorCode: string;
  provenanceUrl?: string;
  frequency: 'annual' | 'quarterly' | 'monthly' | 'daily';
  unit: string;
  description: string;
  points: StandardTimeSeriesPoint[];
}

export interface DiscoveredMotif {
  motifId: string;
  windowSize: number;
  distance: number; // Z-normalized Euclidean distance
  similarityPercentage: number;
  occurrenceA: {
    startIndex: number;
    startDate: string;
    endDate: string;
    rawValues: number[];
    normalizedValues: number[];
  };
  occurrenceB: {
    startIndex: number;
    startDate: string;
    endDate: string;
    rawValues: number[];
    normalizedValues: number[];
  };
  allOccurrences?: Array<{
    index: number;
    date: string;
    distanceToCentroid: number;
  }>;
}

export interface SurrogateNullTest {
  permutationsCount: number;
  observedMotifDistance: number;
  surrogateDistancesMean: number;
  surrogateDistancesStd: number;
  zScore: number;
  pValue: number;
  isStatisticallySignificant: boolean; // p < 0.05
  verdict: 'CONFIRMED_NON_RANDOM_STRUCTURE' | 'REJECTED_AS_STOCHASTIC_NOISE' | 'INCONCLUSIVE_WEAK_SIGNAL';
  scientificNote: string;
}

export interface IntervalEmergenceAnalysis {
  timestamps: string[];
  rawIntervalsDays: number[];
  intervalRatios: number[]; // Delta t_{n+1} / Delta t_n
  meanIntervalDays: number;
  meanRatio: number;
  ratioStdDev: number;
  classification: 'PERIODIC_STABLE' | 'SYSTEMATIC_CONTRACTION' | 'SYSTEMATIC_EXPANSION' | 'STOCHASTIC_DRIFT';
  candidateFormulaDescription: string;
}

export interface DiscoveryExecutionResult {
  seriesId: string;
  seriesName: string;
  totalPoints: number;
  windowSize: number;
  executionTimeMs: number;
  matrixProfileMinDistance: number;
  motifs: DiscoveredMotif[];
  surrogateTest: SurrogateNullTest;
  intervalEmergence?: IntervalEmergenceAnalysis;
}
