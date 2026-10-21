import ast
from pathlib import Path


# Exact acknowledged legacy private edges on the production composition path.
# These are intentionally narrow: removing one is allowed, adding a new one is not.
BASELINE_ACKNOWLEDGED = {
    "api.py": {
        ("_preload", "_app", "db"),
    },
    "cors_app.py": {
        ("_preload", "_global_source_enabled"),
        ("_preload", "_record_blocked_global_source"),
    },
}


def _attribute_chain(node):
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return tuple(reversed(parts))
    return None


def _private_preload_edges(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    observed = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.Attribute) and parent.value is node:
            continue
        chain = _attribute_chain(node)
        if not chain or chain[0] != "_preload" or len(chain) < 2:
            continue
        if chain[1].startswith("_"):
            observed.add(chain)
    return observed


def test_no_new_private_preload_edges_on_runtime_composition_path():
    root = Path(__file__).resolve().parent
    unexpected = {}
    for filename, baseline in BASELINE_ACKNOWLEDGED.items():
        observed = _private_preload_edges(root / filename)
        added = observed - baseline
        if added:
            unexpected[filename] = sorted(".".join(edge) for edge in added)

    assert unexpected == {}, (
        "NEW_PRIVATE_EDGE: runtime composition introduced private preload access "
        f"outside the exact acknowledged baseline: {unexpected}"
    )
