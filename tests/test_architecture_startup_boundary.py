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


def _all_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
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


def test_obsolete_global_worker_thread_hook_is_not_production_reachable():
    """Worker ordering is explicit now; production modules must not install the hook."""
    consumers = {
        path.name
        for path in ROOT.glob("*.py")
        if path.name != "sync_funnel_hook.py" and "sync_funnel_hook" in _all_imports(path)
    }
    assert consumers == set()


def test_app_module_never_starts_its_worker_during_import_or_domain_calls():
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "start_background_worker"
    ]
    assert calls == []


def test_wsgi_starts_worker_only_after_explicit_preload_and_runtime_composition():
    source = (ROOT / "cors_app.py").read_text(encoding="utf-8")

    preload_index = source.index("import preload as _preload")
    init_index = source.index("init_db()")
    final_runtime_index = source.rindex("install_canadabuys_runtime(")
    worker_index = source.rindex("start_background_worker()")

    assert preload_index < init_index < final_runtime_index < worker_index
