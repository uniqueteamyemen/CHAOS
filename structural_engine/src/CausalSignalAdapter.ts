export type NativeSignalClass =
  | "political"
  | "financial"
  | "economic"
  | "collective_behavior"
  | "environmental"
  | "climate"
  | "natural_hazard"
  | "transport"
  | "infrastructure"
  | "conflict"
  | "energy"
  | "trade"
  | "social"
  | "demographic"
  | "systemic_shock"
  | "other";

export interface EvidenceRef {
  sourceId: string;
  sourceUri?: string;
  rawObservationRefs: string[];
  sourceVersion?: string;
  retrievedAt?: string;
}

export interface LagProfile {
  unit: "hours" | "days" | "months";
  median: number;
  lowerQuantile?: number;
  upperQuantile?: number;
  nativeResolution: string;
}

export interface PatternEdge {
  sourceVariableId: string;
  targetVariableId: string;
  lag: LagProfile;
  directScore?: number;
  informationFlowScore?: number;
  statisticalPValue?: number;
  interpretation: "temporal_candidate" | "structural_candidate" | "validated_predictive_edge";
  mediatorCandidates?: string[];
  confounderCandidates?: string[];
}

export interface StructuralPayload {
  patternId: string;
  patternVersion: string;
  triggerEventClass: string;
  nativeSignalClass: NativeSignalClass;
  targetEntity?: {
    domainSpace: string;
    primaryIdentifier: string;
    secondaryIdentifier?: string;
  };
  pathNodes: string[];
  edges: PatternEdge[];
  contributionProfile: Record<string, number>;
  contextProfile: Record<string, string | number | boolean>;
  failureCases: string[];
  uncertainty: Record<string, number | string>;
  sourceConflicts: string[];
  hiddenFactorReference?: string;
  evidence: EvidenceRef[];
  algorithmMetadata: {
    algorithm: string;
    parameters: Record<string, unknown>;
    surrogateMethod?: string;
    surrogateBudget?: number;
    trainingWindow: { start: string; end: string };
    validationWindow?: { start: string; end: string };
  };
  runtimeCompatibility?: {
    signalType: "supply" | "demand";
    reason: string;
    mappingVersion: string;
  };
}

export interface DirectObservationAdapterLike {
  submit(sourceId: string, signal: unknown): Promise<void>;
}

/**
 * Compatibility adapter only. It preserves the native scientific payload and
 * keeps any runtime mapping separate from the scientific meaning.
 */
export class CausalSignalAdapter {
  public readonly id = "structural_autonomous_inference_adapter_v2";

  public constructor(private readonly core: DirectObservationAdapterLike) {}

  public async ingestAutonomousPattern(
    sourceId: string,
    payload: StructuralPayload,
  ): Promise<void> {
    if (!payload.patternId || !payload.patternVersion) {
      throw new Error("Pattern identity and version are required");
    }
    if (payload.pathNodes.length < 2 || payload.edges.length < 1) {
      throw new Error("A structural pattern requires a path and at least one edge");
    }
    if (payload.evidence.length === 0) {
      throw new Error("A structural pattern requires reproducible evidence references");
    }

    const signal = {
      externalReference: payload.patternId,
      evidenceUrl: `system://inference-engine/patterns/${payload.patternId}/versions/${payload.patternVersion}`,
      evidenceClass: "structured_api" as const,
      signalType: payload.runtimeCompatibility?.signalType,
      summary: this.buildSummary(payload),
      metrics: {
        pathNodes: payload.pathNodes,
        edges: payload.edges,
        nativeSignalClass: payload.nativeSignalClass,
        contributionProfile: payload.contributionProfile,
        contextProfile: payload.contextProfile,
        failureCases: payload.failureCases,
        uncertainty: payload.uncertainty,
        sourceConflicts: payload.sourceConflicts,
        hiddenFactorReference: payload.hiddenFactorReference,
        evidence: payload.evidence,
        algorithmMetadata: payload.algorithmMetadata,
        scientificClassification: payload.nativeSignalClass,
        runtimeCompatibility: payload.runtimeCompatibility,
      },
    };

    await this.core.submit(sourceId, signal);
  }

  private buildSummary(payload: StructuralPayload): string {
    const firstEdge = payload.edges[0];
    return [
      `[STRUCTURAL PATTERN] ${payload.patternId}@${payload.patternVersion}`,
      `class=${payload.nativeSignalClass}`,
      `nodes=${payload.pathNodes.length}`,
      `firstLag=${firstEdge.lag.median}${firstEdge.lag.unit}`,
      `interpretation=${firstEdge.interpretation}`,
      `evidenceRefs=${payload.evidence.length}`,
    ].join(" | ");
  }
}
