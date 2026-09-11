"""FR-12 AC2 / §11.3 sandbox static-validation adversarial tests."""
from backend.sandbox.validator import validate_code

ALLOWED_DIRS = ["input", "output"]


def test_clean_template_passes():
    from pathlib import Path
    tpl = Path("backend/sandbox/templates/ndvi_delta_threshold.py")
    assert validate_code(tpl.read_text(encoding="utf-8"), ALLOWED_DIRS) == []


def test_disallowed_import_rejected():
    code = "import socket\n"
    assert any(r.startswith("disallowed_import:socket") for r in
               validate_code(code, ALLOWED_DIRS))


def test_eval_exec_rejected():
    for bad in ("eval('1+1')", "exec('x=1')", "compile('1', '', 'eval')",
                "__import__('os')", "os.system('ls')", "subprocess.run(['ls'])"):
        assert validate_code(f"import numpy as np\n{bad}\n", ALLOWED_DIRS), bad


def test_denied_attribute_access_rejected():
    code = "import numpy as np\nx = os.getcwd\n"
    reasons = validate_code(code, ALLOWED_DIRS)
    assert any("denied_attribute_access:os" in r for r in reasons)


def test_open_outside_sandbox_rejected():
    code = "open('/etc/passwd').read()"
    assert any(r.startswith("open_outside_sandbox") for r in
               validate_code(code, ALLOWED_DIRS))
    ok = 'open("output/result.json", "w")'
    reasons = validate_code(ok, ALLOWED_DIRS)
    assert not any(r.startswith("open_outside_sandbox") for r in reasons)


def test_nonliteral_open_rejected():
    code = "import numpy as np\npath = 'x'\nopen(path).read()"
    assert any("open_with_nonliteral_path" in r for r in
               validate_code(code, ALLOWED_DIRS))


def test_syntax_error_reported():
    assert validate_code("def broken(:\n", ALLOWED_DIRS)[0].startswith("syntax_error")
