from pathlib import Path

from tools.architecture_graph import build_graph


ROOT = Path(__file__).resolve().parents[1]
KNOWN_RUNTIME_CYCLES = [["account_registry.py", "app.py", "company_profile.py"]]


def _edges(graph, source, target):
    return [
        edge
        for edge in graph["edges"]
        if edge["source"] == source and edge["target"] == target
    ]


def _edge(graph, source, target, *, kind=None):
    return next(
        edge
        for edge in _edges(graph, source, target)
        if kind is None or edge["kind"] == kind
    )


def test_dependency_graph_covers_current_runtime_composition_boundaries():
    graph = build_graph(ROOT)

    for node in ("app.py", "api.py", "preload.py", "cors_app.py", "mobile/App.js"):
        assert node in graph["nodes"]

    assert _edge(graph, "render.yaml", "cors_app.py")["classification"] == "EXPECTED"
    assert _edges(graph, "cors_app.py", "sync_funnel_hook.py") == []
    assert _edge(graph, "api.py", "preload.py")["classification"] == "LEGACY"
    assert _edge(graph, "preload.py", "app.py")["classification"] == "LEGACY"
    assert _edge(
        graph,
        "mobile/components/BillingGate.js",
        "mobile/src/billing.js",
        kind="JS_RELATIVE_IMPORT",
    )["classification"] == "EXPECTED"


def test_lazy_schema_composition_edges_are_visible_and_classified():
    graph = build_graph(ROOT)
    edge = _edge(graph, "app.py", "account_registry.py", kind="PYTHON_IMPORT")
    assert edge["scope"] == "LAZY"
    assert edge["classification"] == "LEGACY"


def test_known_runtime_cycle_is_exact_and_does_not_expand():
    graph = build_graph(ROOT)
    assert graph["cycles"] == KNOWN_RUNTIME_CYCLES

    direct_down = _edge(graph, "app.py", "account_registry.py", kind="PYTHON_IMPORT")
    profile_down = _edge(graph, "app.py", "company_profile.py", kind="PYTHON_IMPORT")
    profile_to_account = _edge(
        graph, "company_profile.py", "account_registry.py", kind="PYTHON_IMPORT"
    )
    static_up = _edge(graph, "account_registry.py", "app.py", kind="PYTHON_IMPORT")
    dynamic_up = _edge(graph, "account_registry.py", "app.py", kind="PYTHON_DYNAMIC_IMPORT")

    assert direct_down["scope"] == "LAZY"
    assert profile_down["scope"] == "LAZY"
    assert profile_to_account["scope"] == "LAZY"
    assert static_up["scope"] == "MODULE_LOAD"
    assert dynamic_up["scope"] == "LAZY"
    assert all(
        edge["classification"] == "LEGACY"
        for edge in (direct_down, profile_down, profile_to_account, static_up, dynamic_up)
    )


def test_change_impact_exposes_direct_and_transitive_dependents():
    graph = build_graph(ROOT)
    app_impact = graph["change_impact"]["app.py"]

    assert "account_registry.py" in app_impact["direct_dependents"]
    assert "cors_app.py" in app_impact["direct_dependents"]
    assert "preload.py" in app_impact["direct_dependents"]
    assert "render.yaml" in app_impact["transitive_dependents"]
    assert app_impact["transitive_dependent_count"] >= app_impact["direct_dependent_count"]


def test_unknown_edges_remain_unknown_instead_of_becoming_implicitly_allowed():
    graph = build_graph(ROOT)
    assert any(edge["classification"] == "UNKNOWN" for edge in graph["edges"])
