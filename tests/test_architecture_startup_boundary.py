import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    return imports


def test_implicit_sitecustomize_does_not_import_production_modules():
    """Python auto-loads sitecustomize, so it must not hide app composition edges."""
    local_modules = {path.stem for path in ROOT.glob("*.py")}
    local_modules.discard("sitecustomize")

    implicit_edges = _top_level_imports(ROOT / "sitecustomize.py") & local_modules

    assert implicit_edges == set(), (
        "sitecustomize is an implicit process-wide startup boundary; production "
        f"module imports must be explicit elsewhere, found: {sorted(implicit_edges)}"
    )


def test_worker_start_gate_is_explicit_before_api_composition():
    """The WSGI boundary must install the worker gate before api/app imports."""
    source = (ROOT / "cors_app.py").read_text(encoding="utf-8")

    hook_index = source.index("import sync_funnel_hook")
    api_index = source.index("from api import APP")

    assert hook_index < api_index
