"""GET /api/v1/report/{job_id} — export bundle (FR-18).

PDF + GeoJSON + CSV + generated code + trace, generated purely from persisted
job data (FR-18 AC1) — no pipeline re-run.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

from ..services import job_store
from .errors import problem

router = APIRouter(tags=["report"])


def _safe(text) -> str:
    """Core-font (latin-1) sanitize: never let answer text crash the PDF."""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def _pdf(result: dict) -> bytes:
    from fpdf import FPDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def mc(text: str) -> None:
        # new_x/new_y explicit: default X.RIGHT starves the next width-0 cell
        pdf.multi_cell(0, 6, _safe(text), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 16)
    mc("SatQuery AI - Analysis Report")
    pdf.set_font("Helvetica", "", 11)
    mc(f"Job: {result.get('job_id')}")
    mc(f"Confidence: {result.get('confidence')}   "
       f"Verdict: {result.get('consistency_verdict')}")
    pdf.ln(4)
    mc("Answer:")
    mc(str(result.get("answer", "")))
    pdf.ln(2)
    breakdown = result.get("confidence_breakdown") or {}
    if breakdown:
        mc("Confidence breakdown:")
        for k, v in breakdown.items():
            mc(f"  {k}: {v}")
    pdf.ln(2)
    mc("Agents used: " + ", ".join(result.get("agents_used", [])))
    unc = result.get("uncertainty") or []
    if unc:
        pdf.ln(2)
        mc("Uncertainty notes:")
        for u in unc:
            expl = u.get("explanation", u) if isinstance(u, dict) else u
            mc(f"  - {expl}")
    ev = result.get("evidence") or []
    if ev:
        pdf.ln(2)
        mc("Evidence:")
        for e in ev:
            mc(f"  [{e.get('agent')}] {str(e.get('summary'))[:300]}")
    code = result.get("generated_code") or []
    if code:
        pdf.ln(2)
        mc("Generated analysis code:")
        pdf.set_font("Courier", "", 8)
        for c in code:
            for line in str(c.get("source", "")).splitlines()[:80]:
                mc(line[:110])
        pdf.set_font("Helvetica", "", 11)
    return bytes(pdf.output())


@router.get("/report/{job_id}")
def report(job_id: str):
    job = job_store.get_job(job_id)
    if job is None:
        return problem(404, "Not Found", f"unknown job {job_id}")
    result = job.get("result")
    if not result:
        return problem(409, "Job Not Completed", f"job {job_id} is {job['status']}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("report.pdf", _pdf(result))
        z.writestr("result.json", json.dumps(result, indent=2, default=str))
        z.writestr("execution_trace.json",
                   json.dumps(result.get("execution_trace", []), indent=2))

        # GeoJSON artifacts
        loc = result.get("location") or {}
        if loc.get("features"):
            z.writestr("map_layers.geojson", json.dumps(loc, indent=2))

        # CSV of evidence
        with io.StringIO() as s:
            w = csv.writer(s)
            w.writerow(["agent", "type", "summary", "confidence"])
            for e in result.get("evidence", []):
                w.writerow([e.get("agent"), e.get("type"),
                            str(e.get("summary"))[:500], e.get("confidence")])
            z.writestr("evidence.csv", s.getvalue())

        # Generated code
        for i, c in enumerate(result.get("generated_code", [])):
            z.writestr(f"generated_code_{i}_{c.get('template', 'snippet')}.py",
                       c.get("source", ""))

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=report_{job_id}.zip"},
    )
