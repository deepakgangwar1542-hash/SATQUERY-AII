# tests/e2e/

The PRD (§18) specifies Playwright for browser-driven E2E. Playwright is NOT
installed in this environment (browser binaries are heavy); install with
`npm i -D @playwright/test && npx playwright install chromium` and add specs
here — the frontend dev server and backend URLs match the API proxy config.

Shipped instead: **`scripts/e2e_smoke.py`** — a live-server end-to-end run of
the full §22 loop (upload → NL query → orchestration → result assertions →
report bundle) against a real `uvicorn` process:

```bash
uvicorn backend.main:app --port 8000   # terminal 1
python scripts/e2e_smoke.py            # terminal 2
```

The FastAPI TestClient integration suite in `tests/integration/test_api.py`
covers the same flow in-process for CI.
