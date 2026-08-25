"""Deterministic architecture fitness audit for the ObraSignal modular monolith.

This command intentionally enforces only repository-proven, low-maintenance
invariants. It does not attempt to model every design decision or replace the
canonical queue, capability registry, source registry, ADRs, or runtime modules.

Usage:
    python architecture_audit.py
    python architecture_audit.py --json
    python architecture_audit.py --strict
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shlex
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping


AUDIT_VERSION = "sentinel-architecture-audit.v1"
ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Finding:
    check: str
    category: str
    state: str
    evidence: str
    severity: str = "INFO"


@dataclass(frozen=True)
class AuditReport:
    audit_version: str
    head_sha: str
    status: str
    findings: tuple[Finding, ...]
    violations: tuple[Finding, ...]

    def to_dict(self):
        return {
            "audit_version": self.audit_version,
            "head_sha": self.head_sha,
            "status": self.status,
            "findings": [asdict(item) for item in self.findings],
            "violations": [asdict(item) for item in self.violations],
        }


def _head_sha(root: Path = ROOT) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def _finding(check, category, state, evidence, severity="INFO"):
    return Finding(check, category, state, evidence, severity)


def _queue_contract_violations(items, current_item_id: str) -> list[str]:
    """Validate the canonical queue without inventing a second queue API.

    The queue module intentionally exposes data/query helpers rather than a
    validator function. These checks mirror its already-tested structural
    contract so the architecture audit can fail deterministically when a future
    edit breaks the single-queue invariant.
    """
    problems: list[str] = []
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        seen: set[str] = set()
        duplicates: set[str] = set()
        for item_id in ids:
            if item_id in seen:
                duplicates.add(item_id)
            seen.add(item_id)
        problems.append(f"duplicate queue ids: {sorted(duplicates)}")

    active = [item.id for item in items if item.state == "ACTIVE"]
    if len(active) != 1:
        problems.append(f"expected exactly one ACTIVE item; found {active}")
    elif active[0] != current_item_id:
        problems.append(
            f"CURRENT_ITEM_ID={current_item_id!r} does not match ACTIVE item {active[0]!r}"
        )

    allowed_states = {"DONE", "ACTIVE", "QUEUED", "GATED", "FUTURE"}
    position = {item_id: index for index, item_id in enumerate(ids)}
    for item in items:
        if item.state not in allowed_states:
            problems.append(f"{item.id}: invalid state {item.state!r}")
        for dependency in item.dependencies:
            if dependency not in position:
                problems.append(f"{item.id}: missing dependency {dependency}")
            elif position[dependency] >= position[item.id]:
                problems.append(
                    f"{item.id}: dependency {dependency} is not earlier in canonical order"
                )
    return problems


def _check_queue_contract() -> Iterable[Finding]:
    try:
        from master_execution_queue import CURRENT_ITEM_ID, MASTER_EXECUTION_QUEUE

        problems = _queue_contract_violations(MASTER_EXECUTION_QUEUE, CURRENT_ITEM_ID)
        if problems:
            for problem in problems:
                yield _finding(
                    "master_queue",
                    "CANONICAL_OWNERSHIP",
                    "VIOLATION",
                    problem,
                    "P1",
                )
            return
        active = [item.id for item in MASTER_EXECUTION_QUEUE if item.state == "ACTIVE"]
        yield _finding(
            "master_queue",
            "CANONICAL_OWNERSHIP",
            "HEALTHY",
            f"CURRENT_ITEM_ID={CURRENT_ITEM_ID}; active={active}; ordered_items={len(MASTER_EXECUTION_QUEUE)}",
        )
    except Exception as exc:
        yield _finding(
            "master_queue",
            "CANONICAL_OWNERSHIP",
            "VIOLATION",
            f"canonical queue validation failed: {type(exc).__name__}: {exc}",
            "P1",
        )


def _check_capability_contract() -> Iterable[Finding]:
    try:
        from capability_registry import CAPABILITIES, validate_capability_registry

        validate_capability_registry()
        yield _finding(
            "capability_registry",
            "REGISTRY_DRIFT",
            "HEALTHY",
            f"validated {len(CAPABILITIES)} capability declarations",
        )
    except Exception as exc:
        yield _finding(
            "capability_registry",
            "REGISTRY_DRIFT",
            "VIOLATION",
            f"capability registry validation failed: {type(exc).__name__}: {exc}",
            "P1",
        )


def _source_identity_violations(sources: Mapping[str, Mapping]) -> list[str]:
    seen: dict[str, str] = {}
    problems: list[str] = []
    for key, metadata in sources.items():
        source_id = str(metadata.get("source_id") or "").strip()
        if not source_id:
            problems.append(f"{key}: missing stable source_id")
            continue
        prior = seen.get(source_id)
        if prior is not None and prior != key:
            problems.append(f"duplicate source_id {source_id!r}: {prior}, {key}")
        else:
            seen[source_id] = key
    return problems


def _check_source_identities() -> Iterable[Finding]:
    try:
        from source_registry import SOURCES

        problems = _source_identity_violations(SOURCES)
        if problems:
            for problem in problems:
                yield _finding(
                    "source_identity",
                    "REGISTRY_DRIFT",
                    "VIOLATION",
                    problem,
                    "P1",
                )
            return
        yield _finding(
            "source_identity",
            "REGISTRY_DRIFT",
            "HEALTHY",
            f"{len(SOURCES)} registry entries have non-empty unique stable source_id values",
        )
    except Exception as exc:
        yield _finding(
            "source_identity",
            "REGISTRY_DRIFT",
            "VIOLATION",
            f"source registry could not be validated: {type(exc).__name__}: {exc}",
            "P1",
        )


def _literal_dict_keys(path: Path, assignment_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    keys: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == assignment_name for target in targets):
            continue
        value = node.value
        if not isinstance(value, ast.Dict):
            continue
        for key in value.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.append(key.value)
    return keys


def _duplicate_values(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _check_registry_literal_keys(root: Path = ROOT) -> Iterable[Finding]:
    targets = (
        (root / "source_registry.py", "SOURCES", "source_registry_literal_keys"),
        (root / "capability_registry.py", "CAPABILITIES", "capability_registry_literal_keys"),
    )
    for path, assignment, check in targets:
        try:
            duplicates = _duplicate_values(_literal_dict_keys(path, assignment))
        except (OSError, SyntaxError) as exc:
            yield _finding(
                check,
                "REGISTRY_DRIFT",
                "VIOLATION",
                f"cannot parse {path.name}: {type(exc).__name__}: {exc}",
                "P1",
            )
            continue
        if duplicates:
            yield _finding(
                check,
                "REGISTRY_DRIFT",
                "VIOLATION",
                f"duplicate literal keys in {assignment}: {duplicates}",
                "P1",
            )
        else:
            yield _finding(
                check,
                "REGISTRY_DRIFT",
                "HEALTHY",
                f"no duplicate literal keys in {path.name}:{assignment}",
            )


def _iter_production_python(root: Path) -> Iterable[Path]:
    excluded_parts = {".git", ".venv", "venv", "node_modules", "tests", "__pycache__"}
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if any(part in excluded_parts or part.startswith(".") for part in relative.parts[:-1]):
            continue
        if path.name.startswith("test_"):
            continue
        yield path


def _flask_constructor_lines(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    flask_names = {"Flask"}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "flask":
            for alias in node.names:
                if alias.name == "Flask":
                    flask_names.add(alias.asname or alias.name)
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in flask_names:
            lines.append(node.lineno)
        elif isinstance(func, ast.Attribute) and func.attr == "Flask":
            lines.append(node.lineno)
    return lines


def _check_runtime_single_flask(root: Path = ROOT) -> Iterable[Finding]:
    constructors: list[str] = []
    try:
        for path in _iter_production_python(root):
            for line in _flask_constructor_lines(path):
                constructors.append(f"{path.relative_to(root)}:{line}")
    except (OSError, SyntaxError) as exc:
        yield _finding(
            "single_flask_runtime",
            "RUNTIME_DRIFT",
            "VIOLATION",
            f"runtime scan failed: {type(exc).__name__}: {exc}",
            "P1",
        )
        return
    if len(constructors) != 1 or not constructors[0].startswith("app.py:"):
        yield _finding(
            "single_flask_runtime",
            "RUNTIME_DRIFT",
            "VIOLATION",
            f"expected exactly one production Flask constructor owned by app.py; found {constructors}",
            "P1",
        )
        return
    yield _finding(
        "single_flask_runtime",
        "RUNTIME_DRIFT",
        "HEALTHY",
        f"single production Flask constructor: {constructors[0]}",
    )


def _gunicorn_target(command: str) -> str | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens or Path(tokens[0]).name != "gunicorn":
        return None
    return tokens[-1] if len(tokens) > 1 else None


def _check_render_entrypoint(root: Path = ROOT) -> Iterable[Finding]:
    path = root / "render.yaml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        yield _finding(
            "render_entrypoint",
            "PRODUCTION_CONFIG_DRIFT",
            "VIOLATION",
            f"render.yaml unavailable: {exc}",
            "P1",
        )
        return
    commands = [match.strip() for match in re.findall(r"^\s*startCommand:\s*(.+?)\s*$", text, re.MULTILINE)]
    gunicorn = [(command, _gunicorn_target(command)) for command in commands if _gunicorn_target(command)]
    if len(gunicorn) != 1 or gunicorn[0][1] != "cors_app:APP":
        yield _finding(
            "render_entrypoint",
            "PRODUCTION_CONFIG_DRIFT",
            "VIOLATION",
            f"expected exactly one gunicorn web command targeting cors_app:APP; found {gunicorn}",
            "P1",
        )
        return
    yield _finding(
        "render_entrypoint",
        "PRODUCTION_CONFIG_DRIFT",
        "HEALTHY",
        f"repository-declared production web entrypoint: {gunicorn[0][0]}",
    )


def run_audit(root: Path = ROOT) -> AuditReport:
    findings: list[Finding] = []
    findings.extend(_check_queue_contract())
    findings.extend(_check_capability_contract())
    findings.extend(_check_source_identities())
    findings.extend(_check_registry_literal_keys(root))
    findings.extend(_check_runtime_single_flask(root))
    findings.extend(_check_render_entrypoint(root))
    violations = tuple(item for item in findings if item.state == "VIOLATION")
    return AuditReport(
        audit_version=AUDIT_VERSION,
        head_sha=_head_sha(root),
        status="HEALTHY" if not violations else "DEGRADED",
        findings=tuple(findings),
        violations=violations,
    )


def _human(report: AuditReport) -> str:
    lines = [
        f"ObraSignal Architecture Audit {report.audit_version}",
        f"HEAD: {report.head_sha}",
        f"STATUS: {report.status}",
    ]
    for item in report.findings:
        lines.append(
            f"- [{item.state}] {item.check} / {item.category}: {item.evidence}"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run ObraSignal architecture fitness checks")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when an objectively defined architecture violation is found",
    )
    args = parser.parse_args(argv)
    report = run_audit()
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True) if args.json else _human(report))
    return 1 if args.strict and report.violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
