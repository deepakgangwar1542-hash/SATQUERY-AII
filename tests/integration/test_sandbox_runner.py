"""Sandbox execution tests: output contract + timeout enforcement (FR-12 AC3)."""
from backend.sandbox import runner

GOOD = '''
import json
with open("input/params.json", encoding="utf-8") as fh:
    p = json.load(fh)
with open("output/result.json", "w", encoding="utf-8") as fh:
    json.dump({"answer": p.get("x", 0) * 2}, fh)
'''

LOOP = "while True:\n    pass\n"


def test_sandbox_runs_and_collects_result(tmp_path):
    infile = tmp_path / "a.txt"
    infile.write_text("ok")
    out = runner.run_sandboxed(GOOD, [str(infile)], params={"x": 21})
    assert out["ok"], out
    assert out["outputs"]["result.json"]["answer"] == 42
    assert out["validation_reasons"] == []


def test_sandbox_rejects_disallowed_import():
    out = runner.run_sandboxed("import socket\n", [])
    assert not out["ok"]
    assert out["validation_reasons"]


def test_sandbox_timeout_enforced():
    out = runner.run_sandboxed(LOOP, [], timeout_s=3)
    assert not out["ok"]
    assert "timeout" in out["stderr"]


def test_sandbox_no_stdout_leak_when_empty():
    out = runner.run_sandboxed("import numpy as np\n", [])
    assert not out["ok"]  # §11.3 output contract: no result.json → not ok
