// Typed API client for the SatQuery AI backend (§9).
// In dev, Vite proxies /api and /artifacts to the backend (see vite.config.ts).
import type {
  JobStatus,
  QueryResult,
  UploadedAsset,
  ValidationReport,
} from "./types";

const BASE = "/api/v1";

async function problemOrThrow(res: Response): Promise<never> {
  let detail = res.statusText;
  try {
    const body = await res.json();
    detail = body.detail ?? body.title ?? detail;
  } catch {
    /* non-JSON error body */
  }
  throw new Error(`${res.status}: ${detail}`);
}

export async function uploadRaster(
  file: File,
  sensorType: "optical" | "sar",
  captureDate: string | null,
): Promise<UploadedAsset> {
  const form = new FormData();
  form.append("file", file);
  form.append("sensor_type", sensorType);
  if (captureDate) form.append("capture_date", captureDate);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) await problemOrThrow(res);
  const body = await res.json();
  return {
    asset_id: body.asset_id,
    sensor_type: sensorType,
    capture_date: captureDate ?? undefined,
    name: file.name,
    validation: body.validation as ValidationReport,
  };
}

export async function listAssets(): Promise<UploadedAsset[]> {
  const res = await fetch(`${BASE}/assets`);
  if (!res.ok) return [];
  return res.json();
}

export interface QueryPayload {
  question: string;
  region?: Record<string, unknown> | null;
  assets: { asset_id: string; capture_date?: string; sensor_type: string }[];
}

export async function submitQuery(payload: QueryPayload): Promise<string> {
  const res = await fetch(`${BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) await problemOrThrow(res);
  const body = await res.json();
  return body.job_id as string;
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${BASE}/job/${jobId}`);
  if (!res.ok) await problemOrThrow(res);
  return res.json();
}

export async function getResult(jobId: string): Promise<QueryResult> {
  const res = await fetch(`${BASE}/result/${jobId}`);
  if (!res.ok) await problemOrThrow(res);
  return res.json();
}

export async function getHealth(): Promise<Record<string, any>> {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}

export function jobStreamUrl(jobId: string): string {
  return `${BASE}/job/${jobId}/stream`;
}

export function reportUrl(jobId: string): string {
  return `${BASE}/report/${jobId}`;
}
