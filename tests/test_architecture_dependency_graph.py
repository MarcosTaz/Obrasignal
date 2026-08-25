from pathlib import Path

from tools.architecture_graph import build_graph


ROOT = Path(__file__).resolve().parents[1]
KNOWN_RUNTIME_CYCLES = [["account_registry.py", "app.py"]]


def _edge(graph, source, target):
    return next(
        edge
        for edge in graph["edges"]
        if edge["source"] == source and edge["target"] == target
    )


def test_dependency_graph_covers_current_runtime_composition_boundaries():
    graph = build_graph(ROOT)

    for node in ("app.py", "api.py", "preload.py", "cors_app.py", "mobile/App.js"):
        assert node in graph["nodes"]

    assert _edge(graph, "render.yaml", "cors_app.py")["classification"] == "EXPECTED"
    assert _edge(graph, "cors_app.py", "sync_funnel_hook.py")["classification"] == "EXPECTED"
    assert _edge(graph, "api.py", "preload.py")["classification"] == "LEGACY"
    assert _edge(graph, "preload.py", "app.py")["classification"] == "LEGACY"


def test_lazy_schema_composition_edges_are_visible_and_classified():
    graph = build_graph(ROOT)
    edge = _edge(graph, "app.py", "account_registry.py")
    assert edge["kind"] == "PYTHON_IMPORT"
    assert edge["scope"] == "LAZY"
    assert edge["classification"] == "LEGACY"


def test_known_runtime_cycle_is_exact_and_does_not_expand():
    graph = build_graph(ROOT)
    assert graph["cycles"] == KNOWN_RUNTIME_CYCLES

    down = _edge(graph, "app.py", "account_registry.py")
    up = _edge(graph, "account_registry.py", "app.py")
    assert down["scope"] == "LAZY"
    assert up["scope"] == "MODULE_LOAD"
    assert down["classification"] == "LEGACY"
    assert up["classification"] == "LEGACY"


def test_unknown_edges_remain_unknown_instead_of_becoming_implicitly_allowed():
    graph = build_graph(ROOT)
    assert any(edge["classification"] == "UNKNOWN" for edge in graph["edges"])
