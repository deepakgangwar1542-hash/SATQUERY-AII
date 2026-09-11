/**
 * Shared application types.
 * AppState drives the entire UI state machine.
 */
export type AppState = "idle" | "analyzing" | "result" | "error";

export interface ValidationReport {
  format: string;
  width: number;
  height: number;
  bands: number;
  crs: string;
  resolution_m: number[];
  bounds: number[];
  bounds_wgs84?: number[];
  nodata: number | null;
  sensor_type: string;
  band_mapping_guess: Record<string, number> | null;
  band_mapping_confidence?: string;
  valid: boolean;
  errors: string[];
}

export interface AssetRef {
  asset_id: string;
  capture_date?: string;
  sensor_type: "optical" | "sar";
}

export interface UploadedAsset extends AssetRef {
  name: string;
  validation: ValidationReport;
}

export interface AgentStatus {
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
}

export interface JobStatus {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  agents: AgentStatus[];
  progress_pct: number;
  error?: string | null;
}

export interface TraceEvent {
  timestamp: string;
  agent: string;
  action: string;
  duration_ms: number;
  status: string;
  detail?: string;
}

export interface EvidenceEntry {
  agent: string;
  type: string;
  summary: string;
  confidence?: number;
}

export interface UncertaintyNote {
  signal: string;
  severity: "low" | "medium" | "high";
  explanation: string;
}

export interface GeneratedCode {
  agent: string;
  language: string;
  source: string;
  template?: string;
}

export interface Artifact {
  type: string;
  name: string;
  url: string;
}

export interface SopEntry {
  sop_id: string;
  title: string;
  authority: string;
  domain: string;
  trigger_condition: string;
  action_protocols: string[];
  relevance_score: number;
}

export interface QueryUnderstanding {
  intent: string;
  phenomenon?: string | null;
  target?: string | null;
  temporal: boolean;
  requires_change_detection: boolean;
  requires_sar: boolean;
  requires_gis: boolean;
  summary: string;
}

export interface SensorSelection {
  selected: string[];
  primary: string;
  reason: string;
  sensor_reliability?: Record<string, number>;
  cloud_contamination_optical?: number;
}

export interface InvestigationStep {
  id: string;
  name: string;
  type: string;
  agent: string;
  modality?: string | null;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  summary?: string | null;
  dependencies: string[];
}

export interface InvestigationPlan {
  investigation_id: string;
  mode: "ask" | "investigate" | "explore";
  steps: InvestigationStep[];
  current_iteration?: number;
  max_iterations?: number;
}

export interface Claim {
  id: string;
  text: string;
  evidence_ids: string[];
  numeric_value?: number | null;
  metric_unit?: string | null;
}

export interface HypothesisItem {
  id: string;
  label: string;
  description: string;
  required_evidence: string[];
  support: number;
  evidence_ids: string[];
}

export interface QueryResult {
  job_id: string;
  query?: string;
  query_understanding?: QueryUnderstanding;
  investigation?: InvestigationPlan;
  sensor_selection?: SensorSelection;
  model_selection?: Array<{
    task: string;
    model_name: string;
    modality: string;
    version: string;
    mode: string;
    reason: string;
    gpu_used: boolean;
  }>;
  answer: string;
  claims?: Claim[];
  confidence: number;
  confidence_breakdown: Record<string, number>;
  consistency_verdict: string;
  task_specific_confidence?: {
    score: number;
    level: "high" | "medium" | "low";
    factors: Array<{ factor: string; weight: number; score: number }>;
    limitations: string[];
    policy: string;
  };
  artifacts: Artifact[];
  agents_used: string[];
  plan_rationale?: Record<string, unknown>;
  generated_code: GeneratedCode[];
  uncertainty: UncertaintyNote[];
  location: { type: string; features: GeoJSON.Feature[] };
  evidence: EvidenceEntry[];
  hypotheses?: HypothesisItem[];
  geospatial_results?: {
    affected_building_count?: number;
    total_buildings_detected?: number;
    affected_percentage?: number;
    affected_area_m2?: number;
    formula?: string;
    affected_features_geojson?: { type: string; features: GeoJSON.Feature[] };
  };
  rag_sops?: SopEntry[];
  execution_trace: TraceEvent[];
  follow_up_questions?: string[];
}


// Minimal GeoJSON typings
declare namespace GeoJSON {
  interface Position extends Array<number> {}
  interface PolygonGeometry {
    type: "Polygon";
    coordinates: Position[][];
  }
  interface Feature {
    type: "Feature";
    properties?: Record<string, any>;
    geometry: { type: string; coordinates: any };
  }
  interface FeatureCollection {
    type: "FeatureCollection";
    features: Feature[];
  }
}
