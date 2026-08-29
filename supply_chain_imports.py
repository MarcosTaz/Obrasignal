"""Deterministic Python import/declaration inventory for production modules."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DECLARED_IMPORTS = {
    "Flask": "flask",
    "requests": "requests",
    "gunicorn": "gunicorn",
    "PyJWT[crypto]": "jwt",
}


def declared_requirements() -> dict[str, str]:
    result = {}
    for raw in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        name = re.split(r"[<>=!~]", raw, maxsplit=1)[0].strip()
        result[name] = raw
    return result


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".", 1)[0])
    return names


def inventory() -> dict:
    internal = {path.stem for path in ROOT.glob("*.py")}
    declared = declared_requirements()
    direct_modules = {DECLARED_IMPORTS[name] for name in declared if name in DECLARED_IMPORTS}
    stdlib = set(sys.stdlib_module_names)
    rows = []
    for path in sorted(ROOT.glob("*.py")):
        if path.name.startswith("test_") or path.name in {"conftest.py", "supply_chain_imports.py"}:
            continue
        for name in sorted(_imports(path)):
            if name in internal:
                status = "INTERNAL"
            elif name in stdlib:
                status = "STDLIB"
            elif name in direct_modules:
                status = "DECLARED_DIRECT"
            else:
                status = "TRANSITIVE_LEAK_OR_UNDECLARED"
            rows.append({"file": path.name, "import": name, "status": status})
    return {
        "schema": "obrasignal-python-import-inventory.v1",
        "authority": "observation_only",
        "declared_requirements": declared,
        "imports": rows,
    }


def main() -> None:
    print(json.dumps(inventory(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
