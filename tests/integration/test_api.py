"""API tests — full flow per §18: upload → query → poll → result → report."""
import io
import time

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture()
def client():
    return TestClient(app)


def _upload(client, path, sensor="optical", date=None):
    with open(path, "rb") as fh:
        data = {"file": (path.split("\\")[-1].split("/")[-1], fh,
                         "image/tiff")}
        form = {"sensor_type": sensor}
        if date:
            form["capture_date"] = date
        r = client.post("/api/v1/upload", files=data, data=form)
    assert r.status_code == 200, r.text
    return r.json()["asset_id"]


def _wait(client, job_id, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/v1/job/{job_id}")
        if r.json()["status"] in ("completed", "failed"):
            return r.json()
        time.sleep(0.5)
    raise AssertionError("job did not finish in time")


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["gpu_available"], bool)


def test_upload_rejects_non_raster(client, tmp_path):
    bad = tmp_path / "bad.tif"
    bad.write_bytes(b"garbage" * 100)
    r = client.post("/api/v1/upload",
                    files={"file": ("bad.tif", io.BytesIO(bad.read_bytes()),
                                    "image/tiff")},
                    data={"sensor_type": "optical"})
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")


def test_full_change_query_flow(client, optical_pair):
    a1 = _upload(client, optical_pair["optical_before"], date="2025-06-01")
    a2 = _upload(client, optical_pair["optical_after"], date="2025-09-01")
    r = client.post("/api/v1/query", json={
        "question": "Show areas where vegetation decreased by more than 20% "
                    "between June and September",
        "assets": [{"asset_id": a1, "capture_date": "2025-06-01",
                    "sensor_type": "optical"},
                   {"asset_id": a2, "capture_date": "2025-09-01",
                    "sensor_type": "optical"}]})
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    status = _wait(client, job_id)
    assert status["status"] == "completed", status

    res = client.get(f"/api/v1/result/{job_id}").json()
    assert res["answer"]
    assert 0.0 <= res["confidence"] <= 1.0
    assert res["confidence_breakdown"], "§12.4 breakdown present"
    assert res["execution_trace"], "FR-11 trace present"
    assert "change_agent" in res["agents_used"]
    feats = res["location"]["features"]
    assert feats, "change polygons rendered as features"
    assert feats[0]["geometry"]["coordinates"]

    rep = client.get(f"/api/v1/report/{job_id}")
    assert rep.status_code == 200
    assert rep.headers["content-type"] == "application/zip"
    assert len(rep.content) > 1000


def test_unknown_job_404(client):
    r = client.get("/api/v1/result/job_nope")
    assert r.status_code == 404


def test_query_requires_assets(client):
    r = client.post("/api/v1/query", json={"question": "What is visible?", "assets": []})
    assert r.status_code == 422


def test_execute_analysis_endpoint(client, optical_pair):
    a1 = _upload(client, optical_pair["optical_before"], date="2025-06-01")
    a2 = _upload(client, optical_pair["optical_after"], date="2025-09-01")
    r = client.post("/api/v1/execute-analysis", json={
        "intent": "ndvi_delta_threshold", "asset_ids": [a1, a2],
        "params": {"threshold_pct": -20}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"]
    assert body["generated_code"][0]["language"] == "python"
    assert "result" in body


def test_direct_change_detection(client, optical_pair):
    a1 = _upload(client, optical_pair["optical_before"], date="2025-06-01")
    a2 = _upload(client, optical_pair["optical_after"], date="2025-09-01")
    r = client.post("/api/v1/change-detection", json={
        "image_before_asset_id": a1, "image_after_asset_id": a2})
    assert r.status_code == 200, r.text
    assert r.json()["change_geojson"]["features"]
