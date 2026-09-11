"""End-to-end smoke test against a LIVE backend (tests/e2e/README.md).

Boots nothing itself: start the server first:
    uvicorn backend.main:app --port 8000
then:
    python scripts/e2e_smoke.py [--base http://localhost:8000]

Asserts the §22 core loop: upload pair -> NL query -> poll -> result has
answer/confidence/trace/geojson/code -> report bundle downloads.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def req(url: str, data=None, method=None, headers=None):
    r = Request(url, data=data, method=method,
                headers=headers or {"Content-Type": "application/json"})
    with urlopen(r, timeout=60) as resp:
        return resp.status, resp.read()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    from backend.utils import synth
    import tempfile
    tmp = tempfile.mkdtemp(prefix="satquery_e2e_")
    paths = synth.write_pair(tmp, size=256)

    # 1. health
    status, body = req(f"{base}/api/v1/health")
    health = json.loads(body)
    assert status == 200 and health["status"] == "ok", health
    print(f"[ok] health — gpu={health['gpu_available']}")

    # 2. upload both dates
    def upload(path, sensor, date):
        boundary = "----satquerye2e"
        with open(path, "rb") as fh:
            payload = fh.read()
        parts = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"sensor_type\"\r\n\r\n"
                 f"{sensor}\r\n"
                 f"--{boundary}\r\nContent-Disposition: form-data; name=\"capture_date\"\r\n\r\n"
                 f"{date}\r\n"
                 f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                 f"filename=\"{Path(path).name}\"\r\n"
                 f"Content-Type: image/tiff\r\n\r\n").encode() + payload + f"\r\n--{boundary}--\r\n".encode()
        s, b = req(f"{base}/api/v1/upload", data=parts, method="POST",
                   headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        assert s == 200, b
        return json.loads(b)["asset_id"]

    a1 = upload(paths["optical_before"], "optical", "2025-06-01")
    a2 = upload(paths["optical_after"], "optical", "2025-09-01")
    print(f"[ok] uploaded {a1}, {a2}")

    # 3. submit NL change query
    query = {
        "question": "Show areas where vegetation decreased by more than 20% "
                    "between June and September",
        "assets": [
            {"asset_id": a1, "capture_date": "2025-06-01", "sensor_type": "optical"},
            {"asset_id": a2, "capture_date": "2025-09-01", "sensor_type": "optical"},
        ],
    }
    s, b = req(f"{base}/api/v1/query", data=json.dumps(query).encode(), method="POST")
    job_id = json.loads(b)["job_id"]
    print(f"[ok] job {job_id} queued")

    # 4. poll (tolerate transient 404/decode races during persistence)
    deadline = time.time() + 180
    j = None
    while time.time() < deadline:
        try:
            _, b = req(f"{base}/api/v1/job/{job_id}")
            j = json.loads(b)
            if j["status"] in ("completed", "failed"):
                break
        except Exception:
            pass
        time.sleep(1)
    assert j is not None and j["status"] == "completed", j
    print(f"[ok] job completed — agents: {[a['name'] for a in j['agents']]}")

    # 5. result assertions (§22)
    s, b = req(f"{base}/api/v1/result/{job_id}")
    r = json.loads(b)
    assert r["answer"] and 0 <= r["confidence"] <= 1
    assert r["execution_trace"] and r["evidence"]
    assert r["location"]["features"], "no geojson features"
    assert r["generated_code"], "no generated code"
    assert r["confidence_breakdown"]
    print(f"[ok] result — confidence={r['confidence']} "
          f"verdict={r['consistency_verdict']} features={len(r['location']['features'])}")

    # 6. report bundle
    s, b = req(f"{base}/api/v1/report/{job_id}")
    assert s == 200 and len(b) > 1000
    print(f"[ok] report bundle: {len(b)} bytes")

    print("\nE2E SMOKE PASS")


if __name__ == "__main__":
    main()
