#!/usr/bin/env python3
"""Deterministic internal dependency graph for ObraSignal.

The scanner is intentionally dependency-free. It discovers production Python
imports, literal dynamic Python imports, relative Mobile JS/TS imports and the
Render WSGI entrypoint. Edges are UNKNOWN unless a narrow repository-proven
policy classifies them.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable


JS_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
EDGE_POLICY = {
    ("render.yaml", "cors_app.py"): "EXPECTED",
    ("cors_app.py", "api.py"): "EXPECTED",
    ("cors_app.py", "app.py"): "EXPECTED",
    ("cors_app.py", "preload.py"): "EXPECTED",
    ("preload.py", "app.py"): "LEGACY",
    ("api.py", "preload.py"): "LEGACY",
    ("app.py", "account_registry.py"): "LEGACY",
    ("account_registry.py", "app.py"): "LEGACY",
    ("app.py", "company_profile.py"): "LEGACY",
    ("company_profile.py", "account_registry.py"): "LEGACY",
    ("app.py", "decision_log.py"): "LEGACY",
    ("app.py", "latency_metrics.py"): "LEGACY",
    ("app.py", "notification_events.py"): "LEGACY",
    ("app.py", "opportunity_workflow.py"): "LEGACY",
    ("app.py", "source_health.py"): "LEGACY",
    ("mobile/components/BillingGate.js", "mobile/src/billing.js"): "EXPECTED",
}


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_test_path(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    return (
        "tests" in rel.parts
        or path.name.startswith("test_")
        or ".test." in path.name
        or path.name == "conftest.py"
    )


def discover_production_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.glob("*.py"):
        if not _is_test_path(path, root):
            files.append(path)
    mobile = root / "mobile"
    if mobile.exists():
        for path in mobile.rglob("*"):
            if not path.is_file() or path.suffix not in JS_EXTENSIONS:
                continue
            if "node_modules" in path.parts or _is_test_path(path, root):
                continue
            files.append(path)
    return sorted(files, key=lambda p: _rel(p, root))


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.function_depth = 0
        self.imports: list[tuple[str, str, str]] = []

    def _scope(self) -> str:
        return "LAZY" if self.function_depth else "MODULE_LOAD"

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append((alias.name, self._scope(), "PYTHON_IMPORT"))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.append((node.module, self._scope(), "PYTHON_IMPORT"))

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            self.imports.append(
                (node.args[0].value, self._scope(), "PYTHON_DYNAMIC_IMPORT")
            )
        self.generic_visit(node)


def _python_module_map(files: Iterable[Path], root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in files:
        if path.suffix != ".py":
            continue
        rel = path.relative_to(root)
        if len(rel.parts) == 1:
            result[path.stem] = rel.as_posix()
    return result


def _python_edges(path: Path, root: Path, module_map: dict[str, str]) -> list[dict]:
    visitor = _ImportVisitor()
    visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
    source = _rel(path, root)
    edges = []
    for module, scope, kind in visitor.imports:
        target = module_map.get(module.split(".", 1)[0])
        if not target or target == source:
            continue
        edges.append(
            {
                "source": source,
                "target": target,
                "kind": kind,
                "scope": scope,
                "classification": EDGE_POLICY.get((source, target), "UNKNOWN"),
            }
        )
    return edges


_JS_IMPORT_RE = re.compile(
    r"(?:\bfrom\s+|\bimport\s*\(|\brequire\s*\()\s*[\"']([^\"']+)[\"']"
)
_SIDE_EFFECT_IMPORT_RE = re.compile(r"\bimport\s*[\"']([^\"']+)[\"']")


def _resolve_js_relative(source: Path, specifier: str, root: Path) -> str | None:
    if not specifier.startswith("."):
        return None
    base = (source.parent / specifier).resolve()
    candidates = [base]
    candidates.extend(Path(str(base) + suffix) for suffix in JS_EXTENSIONS)
    candidates.extend(base / ("index" + suffix) for suffix in JS_EXTENSIONS)
    for candidate in candidates:
        if candidate.is_file():
            try:
                return _rel(candidate, root)
            except ValueError:
                return None
    return None


def _js_edges(path: Path, root: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    specs = set(_JS_IMPORT_RE.findall(text)) | set(_SIDE_EFFECT_IMPORT_RE.findall(text))
    source = _rel(path, root)
    edges = []
    for specifier in sorted(specs):
        target = _resolve_js_relative(path, specifier, root)
        if not target or target == source:
            continue
        edges.append(
            {
                "source": source,
                "target": target,
                "kind": "JS_RELATIVE_IMPORT",
                "scope": "MODULE_LOAD",
                "classification": EDGE_POLICY.get((source, target), "UNKNOWN"),
            }
        )
    return edges


def _render_entrypoint_edge(root: Path) -> list[dict]:
    render = root / "render.yaml"
    if not render.exists():
        return []
    text = render.read_text(encoding="utf-8")
    match = re.search(r"\bgunicorn\b[^\n]*\b([A-Za-z_]\w*):([A-Za-z_]\w*)", text)
    if not match:
        return []
    module_path = root / f"{match.group(1)}.py"
    if not module_path.exists():
        return []
    source, target = "render.yaml", module_path.name
    return [
        {
            "source": source,
            "target": target,
            "kind": "RUNTIME_ENTRYPOINT",
            "scope": "STARTUP",
            "classification": EDGE_POLICY.get((source, target), "UNKNOWN"),
        }
    ]


def _cycles(nodes: list[str], edges: list[dict]) -> list[list[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge["kind"] == "RUNTIME_ENTRYPOINT":
            continue
        graph[edge["source"]].add(edge["target"])

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    components: list[list[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = lowlink[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(graph.get(node, ())):
            if target not in indices:
                strongconnect(target)
                lowlink[node] = min(lowlink[node], lowlink[target])
            elif target in on_stack:
                lowlink[node] = min(lowlink[node], indices[target])
        if lowlink[node] == indices[node]:
            component = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1:
                components.append(sorted(component))

    for node in sorted(nodes):
        if node not in indices:
            strongconnect(node)
    return sorted(components)


def _change_impact(nodes: list[str], edges: list[dict]) -> dict[str, dict]:
    reverse: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        reverse[edge["target"]].add(edge["source"])

    impact: dict[str, dict] = {}
    for node in sorted(nodes):
        direct = sorted(reverse.get(node, ()))
        seen: set[str] = set()
        stack = list(direct)
        while stack:
            dependent = stack.pop()
            if dependent == node or dependent in seen:
                continue
            seen.add(dependent)
            stack.extend(reverse.get(dependent, ()))
        impact[node] = {
            "direct_dependents": direct,
            "direct_dependent_count": len(direct),
            "transitive_dependents": sorted(seen),
            "transitive_dependent_count": len(seen),
        }
    return impact


def build_graph(root: Path) -> dict:
    root = root.resolve()
    files = discover_production_files(root)
    module_map = _python_module_map(files, root)
    nodes = [_rel(path, root) for path in files]
    if (root / "render.yaml").exists():
        nodes.append("render.yaml")

    edges: list[dict] = []
    for path in files:
        if path.suffix == ".py":
            edges.extend(_python_edges(path, root, module_map))
        else:
            edges.extend(_js_edges(path, root))
    edges.extend(_render_entrypoint_edge(root))

    deduped = {
        (e["source"], e["target"], e["kind"], e["scope"], e["classification"]): e
        for e in edges
    }
    edges = sorted(
        deduped.values(),
        key=lambda e: (e["source"], e["target"], e["kind"], e["scope"]),
    )
    nodes = sorted(set(nodes))
    return {
        "schema_version": 1,
        "repository_sha": os.getenv("OBRASIGNAL_TEST_SHA", "UNKNOWN"),
        "coverage": [
            "ROOT_PYTHON",
            "LITERAL_PYTHON_DYNAMIC_IMPORTS",
            "MOBILE_RELATIVE_JS_TS",
            "RENDER_WSGI_ENTRYPOINT",
        ],
        "nodes": nodes,
        "edges": edges,
        "cycles": _cycles(nodes, edges),
        "change_impact": _change_impact(nodes, edges),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()
    graph = build_graph(Path(args.root))
    text = json.dumps(graph, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
