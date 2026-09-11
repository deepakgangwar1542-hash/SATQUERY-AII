"""Sandboxed execution harness — implements PRD FR-12 AC3 and §11.3.

Generated code never runs in the API process (§7.3): it is written into a
per-job temp directory together with read-only copies of the approved input
rasters, and executed in an isolated subprocess that must write its results
to `result.json` / `output.geojson` / `output.tif` in the output directory
(§11.3 output contract).

Isolation levels by platform:
  * Linux/Docker (the supported deployment, §19): CPU (`RLIMIT_CPU`), memory
    (`RLIMIT_AS`), process-count (`RLIMIT_NPROC`) limits via preexec_fn, plus
    `--network none` / no network namespace in the container runtime.
  * Windows (dev convenience): wall-clock timeout and sanitized environment
    are enforced; rlimits are unavailable on this platform — the Docker
    deployment is the security boundary (documented in README).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .validator import validate_code

if os.name == "posix":
    import resource  # noqa: F401  (used in _posix_limits)

DEFAULT_TIMEOUT_S = 30
DEFAULT_MEMORY_MB = 2048

SANDBOX_ENV = {
    "PATH": os.environ.get("PATH", ""),
    "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),   # needed by Python on Windows
    "SATQUERY_SANDBOX": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}


def _posix_limits(memory_mb: int, cpu_seconds: int):
    def apply():  # runs in the child before exec (POSIX only)
        mem = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 2))
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        except (ValueError, OSError):
            pass
        os.setpgrp()
    return apply


def run_sandboxed(code: str, input_files: list[str], params: dict | None = None,
                  timeout_s: int = DEFAULT_TIMEOUT_S,
                  memory_mb: int = DEFAULT_MEMORY_MB) -> dict:
    """Validate then execute generated code. Returns a result envelope:
    {ok, exit_code, duration_ms, stdout, stderr, validation_reasons, outputs}."""
    reasons = validate_code(
        code,
        allowed_open_dirs=["input", "output"],  # relative prefixes used by templates
    )
    if reasons:
        return {"ok": False, "exit_code": None, "duration_ms": 0, "stdout": "",
                "stderr": "", "validation_reasons": reasons, "outputs": {}}

    with tempfile.TemporaryDirectory(prefix="satquery_sandbox_") as tmp:
        workdir = Path(tmp)
        in_dir = workdir / "input"
        out_dir = workdir / "output"
        in_dir.mkdir()
        out_dir.mkdir()

        # Only the job's approved inputs are visible, copied read-only (§11.3).
        for f in input_files:
            dest = in_dir / Path(f).name
            shutil.copyfile(f, dest)
            os.chmod(dest, 0o444)

        script = workdir / "analysis.py"
        script.write_text(code, encoding="utf-8")
        (in_dir / "params.json").write_text(
            json.dumps(params or {}), encoding="utf-8")

        cmd = [sys.executable, "-I", str(script)]
        preexec = None
        if os.name == "posix":
            preexec = _posix_limits(memory_mb, timeout_s)

        started = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=str(workdir), env=SANDBOX_ENV.copy(),
                capture_output=True, text=True, timeout=timeout_s,
                preexec_fn=preexec,
            )
            exit_code, stdout, stderr = proc.returncode, proc.stdout[-8000:], proc.stderr[-8000:]
        except subprocess.TimeoutExpired as exc:
            return {"ok": False, "exit_code": None,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "stdout": (exc.stdout or b"").decode()[-2000:] if isinstance(exc.stdout, bytes) else str(exc.stdout or ""),
                    "stderr": f"timeout_after_{timeout_s}s",
                    "validation_reasons": [], "outputs": {}}
        duration_ms = int((time.monotonic() - started) * 1000)

        outputs: dict = {}
        for name in ("result.json", "output.geojson"):
            p = out_dir / name
            if p.exists():
                try:
                    outputs[name] = json.loads(p.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    outputs[name] = {"error": f"unparsable_{name}"}
        if (out_dir / "output.tif").exists():
            outputs["output.tif"] = f"output/{'output.tif'}"

        return {"ok": exit_code == 0 and bool(outputs), "exit_code": exit_code,
                "duration_ms": duration_ms, "stdout": stdout, "stderr": stderr,
                "validation_reasons": [], "outputs": outputs}
