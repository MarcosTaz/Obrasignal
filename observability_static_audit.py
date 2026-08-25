"""Repository-local static audit for operational silence and unsafe diagnostics.

The audit is intentionally read-only. It reports bounded metadata (file, function,
line, finding code) and never evaluates code or prints runtime values, secrets,
customer payloads, exception text, or source-line contents.
"""
from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


CONTRACT_VERSION = "observability-static-audit-v0"


@dataclass(frozen=True)
class AuditFinding:
    code: str
    path: str
    function: str
    line: int
    severity: str
    owner_hint: str


def _function_name(parents: list[ast.AST]) -> str:
    for node in reversed(parents):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return "<module>"


def _name_matches(node: ast.AST, name: str | None) -> bool:
    return bool(name) and isinstance(node, ast.Name) and node.id == name


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _raw_exception_call(handler: ast.ExceptHandler, parents: list[ast.AST], path: str) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    exc_name = handler.name if isinstance(handler.name, str) else None
    if not exc_name:
        return findings

    function = _function_name(parents)
    for node in ast.walk(handler):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node)

        if call_name == "print" and any(_name_matches(arg, exc_name) for arg in node.args):
            findings.append(
                AuditFinding(
                    code="RAW_EXCEPTION_STDOUT",
                    path=path,
                    function=function,
                    line=getattr(node, "lineno", getattr(handler, "lineno", 0)),
                    severity="PRIVACY_REVIEW",
                    owner_hint="OBSERVABILITY_SECURITY_PRIVACY",
                )
            )

        for keyword in node.keywords:
            if keyword.arg not in {"error", "exception", "detail", "message"}:
                continue
            raw_exception = _name_matches(keyword.value, exc_name)
            raw_exception = raw_exception or (
                isinstance(keyword.value, ast.Call)
                and _call_name(keyword.value) == "str"
                and any(_name_matches(arg, exc_name) for arg in keyword.value.args)
            )
            if raw_exception:
                findings.append(
                    AuditFinding(
                        code="RAW_EXCEPTION_SINK",
                        path=path,
                        function=function,
                        line=getattr(node, "lineno", getattr(handler, "lineno", 0)),
                        severity="PRIVACY_REVIEW",
                        owner_hint="OBSERVABILITY_SECURITY_PRIVACY",
                    )
                )
    return findings


def scan_python_source(path: str, source: str) -> list[AuditFinding]:
    """Scan one Python source file without returning source text or values."""

    tree = ast.parse(source, filename=path)
    findings: list[AuditFinding] = []

    def visit(node: ast.AST, parents: list[ast.AST]):
        if isinstance(node, ast.ExceptHandler):
            function = _function_name(parents)
            meaningful = [item for item in node.body if not isinstance(item, ast.Pass)]
            if node.body and not meaningful:
                findings.append(
                    AuditFinding(
                        code="SILENT_EXCEPTION_PASS",
                        path=path,
                        function=function,
                        line=getattr(node, "lineno", 0),
                        severity="DIAGNOSTIC_GAP",
                        owner_hint="OBSERVABILITY_OR_DOMAIN_OWNER",
                    )
                )
            findings.extend(_raw_exception_call(node, parents, path))

        for child in ast.iter_child_nodes(node):
            visit(child, parents + [node])

    visit(tree, [])
    return sorted(findings, key=lambda item: (item.path, item.line, item.code))


def scan_python_files(repo_root: str | Path, paths: Iterable[str]) -> list[AuditFinding]:
    root = Path(repo_root)
    findings: list[AuditFinding] = []
    for relative in sorted(set(paths)):
        source = (root / relative).read_text(encoding="utf-8")
        findings.extend(scan_python_source(relative, source))
    return sorted(findings, key=lambda item: (item.path, item.line, item.code))


def current_repository_report(repo_root: str | Path = ".") -> dict:
    """Audit current high-value operational paths with bounded output only."""

    paths = ("app.py", "preload.py", "source_health.py")
    findings = scan_python_files(repo_root, paths)
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.code] = counts.get(finding.code, 0) + 1
    return {
        "contract_version": CONTRACT_VERSION,
        "paths": list(paths),
        "counts": counts,
        "findings": [asdict(item) for item in findings],
    }


if __name__ == "__main__":
    print(json.dumps(current_repository_report(), sort_keys=True, separators=(",", ":")))
