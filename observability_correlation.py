"""Privacy-safe operational correlation contracts for ObraSignal.

Domain identity, idempotency identity and operational correlation are deliberately
kept separate.  A useful domain key is not automatically safe to place in logs.
"""
from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping


CORRELATION_CONTRACT_VERSION = "observability-correlation-v0"
CORRELATION_NAMES = frozenset({"correlation_id", "request_id", "operation_id", "trace_id"})


@dataclass(frozen=True)
class CorrelationAssessment:
    name: str
    classification: str
    opaque: bool
    embeds_tenant_identity: bool
    embeds_domain_identity: bool
    customer_content: bool
    stable_one_operation: bool
    reusable_as_operational_correlation: bool
    reasons: tuple[str, ...]


def assess_correlation_candidate(
    name: str,
    *,
    opaque: bool,
    embeds_tenant_identity: bool = False,
    embeds_domain_identity: bool = False,
    customer_content: bool = False,
    stable_one_operation: bool = False,
) -> CorrelationAssessment:
    """Classify an identifier without inspecting or returning its runtime value."""

    if not name or len(name) > 64:
        raise ValueError("correlation candidate name must be non-empty and bounded")

    reasons: list[str] = []
    reusable = True
    if customer_content:
        reasons.append("CUSTOMER_CONTENT")
        reusable = False
    if embeds_tenant_identity:
        reasons.append("TENANT_IDENTITY_EMBEDDED")
        reusable = False
    if embeds_domain_identity:
        reasons.append("DOMAIN_IDENTITY_EMBEDDED")
        reusable = False
    if not opaque:
        reasons.append("NOT_OPAQUE")
        reusable = False
    if not stable_one_operation:
        reasons.append("LOGICAL_OPERATION_SCOPE_UNPROVEN")
        reusable = False

    if customer_content or embeds_tenant_identity:
        classification = "UNSAFE_AS_CORRELATION"
    elif embeds_domain_identity or not opaque:
        classification = "DOMAIN_ID_NOT_CORRELATION"
    elif not stable_one_operation:
        classification = "UNKNOWN"
    else:
        classification = "SAFE_CORRELATION"

    return CorrelationAssessment(
        name=name,
        classification=classification,
        opaque=opaque,
        embeds_tenant_identity=embeds_tenant_identity,
        embeds_domain_identity=embeds_domain_identity,
        customer_content=customer_content,
        stable_one_operation=stable_one_operation,
        reusable_as_operational_correlation=reusable,
        reasons=tuple(reasons),
    )


def _assigned_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


def _joined_string_names(value: ast.AST) -> set[str]:
    names: set[str] = set()
    if not isinstance(value, ast.JoinedStr):
        return names
    for child in ast.walk(value):
        if isinstance(child, ast.Name):
            names.add(child.id)
    return names


def scan_notification_event_key(source: str) -> CorrelationAssessment:
    """Classify the notification ``event_key`` shape without reading event data."""

    tree = ast.parse(source)
    tenant_embedded = False
    domain_embedded = False
    found = False
    for node in ast.walk(tree):
        targets = []
        value = None
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if value is None or not any(_assigned_name(target) == "event_key" for target in targets):
            continue
        found = True
        names = _joined_string_names(value)
        tenant_embedded = tenant_embedded or "account_id" in names
        domain_embedded = domain_embedded or bool(names & {"base_key", "external_id", "source", "tender_id"})

    if not found:
        return assess_correlation_candidate(
            "notification_event_key",
            opaque=False,
            stable_one_operation=False,
        )
    return assess_correlation_candidate(
        "notification_event_key",
        opaque=False,
        embeds_tenant_identity=tenant_embedded,
        embeds_domain_identity=domain_embedded,
        stable_one_operation=False,
    )


def scan_request_correlation(sources: Mapping[str, str]) -> dict:
    """Inventory explicit request/operation correlation identifiers by source file."""

    found: dict[str, list[str]] = {}
    for filename, source in sources.items():
        tree = ast.parse(source)
        names = {
            child.id
            for child in ast.walk(tree)
            if isinstance(child, ast.Name) and child.id in CORRELATION_NAMES
        }
        attrs = {
            child.attr
            for child in ast.walk(tree)
            if isinstance(child, ast.Attribute) and child.attr in CORRELATION_NAMES
        }
        present = sorted(names | attrs)
        if present:
            found[str(filename)] = present
    return {
        "state": "PROVEN" if found else "UNKNOWN",
        "identifiers": found,
        "finding": None if found else "NO_EXPLICIT_REQUEST_CORRELATION",
    }


def current_repository_correlation_report(repo_root: str | Path = ".") -> dict:
    """Return a secret-free repository-only correlation inventory."""

    root = Path(repo_root)
    notification_source = (root / "notification_events.py").read_text(encoding="utf-8")
    request_sources = {
        "api.py": (root / "api.py").read_text(encoding="utf-8"),
        "app.py": (root / "app.py").read_text(encoding="utf-8"),
        "cors_app.py": (root / "cors_app.py").read_text(encoding="utf-8"),
    }
    return {
        "contract_version": CORRELATION_CONTRACT_VERSION,
        "request": scan_request_correlation(request_sources),
        "notification_event_key": asdict(scan_notification_event_key(notification_source)),
    }


if __name__ == "__main__":
    print(json.dumps(current_repository_correlation_report(), sort_keys=True, separators=(",", ":")))
