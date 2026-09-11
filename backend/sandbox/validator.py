"""Static AST validation for sandboxed GIS code — implements PRD FR-12 AC2
and §11.3. Runs BEFORE any execution; rejection reasons are logged and can be
fed back to the code-generation agent once (§12.3).

Whitelist imports: numpy, rasterio, geopandas, shapely, pandas (FR-12 AC1).
Denylist calls: eval/exec/compile/__import__/os.system/subprocess/socket.
`open()` may only target paths inside the job's sandbox input/output dirs.
"""
from __future__ import annotations

import ast

ALLOWED_IMPORTS = {"numpy", "rasterio", "geopandas", "shapely", "pandas"}
ALLOWED_IMPORT_ROOTS = ALLOWED_IMPORTS | {"math", "json"}  # stdlib shims used by templates
DENIED_CALLS = {"eval", "exec", "compile", "__import__", "input", "open"}
DENIED_ROOT_ATTRS = {"os", "sys", "socket", "subprocess", "shutil", "pathlib",
                     "requests", "urllib", "http", "ctypes", "importlib"}
ALLOWED_OPEN_PREFIXES: tuple[str, ...] = ()  # set per job (sandbox in/out dirs)


class ValidationFailure(Exception):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def _resolve_root(node: ast.AST) -> str | None:
    """Resolve the root name of a Name/Attribute chain (e.g. `np.linalg` → numpy alias)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _resolve_root(node.value)
    return None


def validate_code(source: str, allowed_open_dirs: list[str] | None = None) -> list[str]:
    """Return a list of rejection reasons; empty list means the code is safe."""
    reasons: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"syntax_error:{exc}"]

    allowed_dirs = [str(p) for p in (allowed_open_dirs or [])]

    for node in ast.walk(tree):
        # --- imports (FR-12 AC1) ---
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_IMPORT_ROOTS:
                    reasons.append(f"disallowed_import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root and root not in ALLOWED_IMPORT_ROOTS:
                reasons.append(f"disallowed_import:from {node.module}")

        # --- denied calls ---
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                name = fn.id
                if name in DENIED_CALLS:
                    if name == "open":
                        if not node.args:
                            reasons.append("open_without_args")
                        else:
                            first = node.args[0]
                            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                                if not any(first.value.startswith(d) for d in allowed_dirs):
                                    reasons.append(f"open_outside_sandbox:{first.value}")
                            elif not isinstance(first, ast.Constant):
                                reasons.append("open_with_nonliteral_path")
                    else:
                        reasons.append(f"denied_call:{name}")
            elif isinstance(fn, ast.Attribute):
                # e.g. `rasterio.open`, `gdf.to_crs` — allowed unless the ROOT
                # is a denied module (os./sys./socket./... defense-in-depth;
                # the import whitelist already blocks importing them).
                root = _resolve_root(fn)
                if root in DENIED_ROOT_ATTRS:
                    reasons.append(f"denied_attribute_access:{root}")

        # --- attribute access on denied roots (e.g. `os.getcwd` without call) ---
        elif isinstance(node, ast.Attribute):
            root = _resolve_root(node)
            if root in DENIED_ROOT_ATTRS:
                reasons.append(f"denied_attribute_access:{root}.{node.attr}")

    return reasons
