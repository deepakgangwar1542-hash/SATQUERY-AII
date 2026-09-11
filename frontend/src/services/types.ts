// Shared API types — mirrors backend §9.2/§9.3 response schemas.
// (Hand-written rather than generated from the FastAPI OpenAPI schema;
// swap to openapi-typescript later if drift becomes a problem.)

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

export interface QueryResult {
  job_id: string;
  answer: string;
  confidence: number;
  confidence_breakdown: Record<string, number>;
  consistency_verdict: string;
  artifacts: Artifact[];
  agents_used: string[];
  plan_rationale?: Record<string, unknown>;
  generated_code: GeneratedCode[];
  uncertainty: UncertaintyNote[];
  location: { type: string; features: GeoJSON.Feature[] };
  evidence: EvidenceEntry[];
  execution_trace: TraceEvent[];
}

// Minimal GeoJSON typings (only what we consume)
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
