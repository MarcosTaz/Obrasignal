from __future__ import annotations

from .models import CompanyManifest, Evidence, Risk, TruthState


LIVE_KINDS = {"live_adapter", "factory_feed", "business_metric_feed", "operational_metric_feed", "risk_feed"}
AUTHORITATIVE_RISK_KINDS = {"risk_feed", "live_adapter"}


def risk_current_state(risk: Risk) -> TruthState:
    """Evaluate whether a risk is proven current, stale, or still only contextual.

    A severity label can describe the impact *if* a risk is present. It is not proof
    that the risk is currently active. Context/manual/bootstrap evidence therefore
    stays UNKNOWN for current-risk truth; only explicit live risk evidence can be
    current, and its normal freshness rules still apply.
    """
    evidence = risk.evidence
    if evidence is None or evidence.kind not in AUTHORITATIVE_RISK_KINDS:
        return TruthState.UNKNOWN
    return evidence.freshness_state()


def risk_view(risk: Risk) -> dict:
    current = risk_current_state(risk)
    return {
        "title": risk.title,
        "severity": risk.severity,
        "category": risk.category,
        "detail": risk.detail,
        "current_truth": current.value,
        "source": risk.evidence.source if risk.evidence else "UNKNOWN",
        "source_kind": risk.evidence.kind if risk.evidence else "unknown",
        "observed_at": risk.evidence.observed_at if risk.evidence else None,
    }


def company_api_view(company: CompanyManifest) -> dict:
    """Return one normalized company payload without losing derived truth semantics."""
    payload = company.to_dict()
    payload["risks"] = [risk_view(risk) for risk in company.risks]
    return payload


def _entry(label: str, category: str, evidence: Evidence | None, claimed_state: str | None = None, current_truth: str | None = None) -> dict:
    if evidence is None:
        return {
            "label": label,
            "category": category,
            "source": "UNKNOWN",
            "kind": "unknown",
            "observed_at": None,
            "freshness_seconds": None,
            "freshness": TruthState.UNKNOWN.value,
            "claimed_state": claimed_state or "UNKNOWN",
            "current_truth": current_truth or "UNKNOWN",
        }
    return {
        "label": label,
        "category": category,
        "source": evidence.source,
        "kind": evidence.kind,
        "observed_at": evidence.observed_at,
        "freshness_seconds": evidence.freshness_seconds,
        "freshness": evidence.freshness_state().value,
        "claimed_state": claimed_state or "UNKNOWN",
        "current_truth": current_truth or claimed_state or "UNKNOWN",
    }


def source_inventory(company: CompanyManifest) -> list[dict]:
    """Describe provenance without treating the control center itself as source authority."""
    entries = [
        _entry("Revenue", "business", company.revenue.evidence, company.revenue.state.value),
        _entry("Pipeline", "business", company.pipeline.evidence, company.pipeline.state.value),
        _entry("Customers", "business", company.customers.evidence, company.customers.state.value),
        _entry("Repository / CI", "engineering", company.repository.evidence, company.repository.ci.value),
        _entry("Deployment", "engineering", company.application.deployment_evidence, company.application.deployment.value),
        _entry("Application health", "product", company.application.health_evidence, company.application.health.value),
    ]
    for metric in company.metrics:
        entries.append(_entry(metric.label, "metric", metric.evidence, metric.state.value))
    for factory in company.factories:
        entries.append(_entry(f"Factory: {factory.name}", "factory", factory.evidence, factory.freshness.value))
    for risk in company.risks:
        entries.append(_entry(
            f"Risk: {risk.title}",
            "risk",
            risk.evidence,
            risk.severity,
            risk_current_state(risk).value,
        ))
    return entries


def _source_identity(item: dict) -> tuple[str, str]:
    return str(item.get("kind", "unknown")), str(item.get("source", "UNKNOWN"))


def source_summary(company: CompanyManifest) -> dict:
    entries = source_inventory(company)
    counts = {state.value: 0 for state in TruthState}
    for item in entries:
        counts[item["freshness"]] = counts.get(item["freshness"], 0) + 1
    connected = [item for item in entries if item["kind"] in LIVE_KINDS]
    fresh_connected = [item for item in connected if item["freshness"] == TruthState.GREEN.value]
    connected_sources = {_source_identity(item) for item in connected}
    fresh_sources = {_source_identity(item) for item in fresh_connected}
    return {
        "company_id": company.id,
        "total": len(entries),
        "connected_boundary_count": len(connected),
        "fresh_live_boundary_count": len(fresh_connected),
        "connected_source_count": len(connected_sources),
        "fresh_live_source_count": len(fresh_sources),
        "live_source_count": len(fresh_sources),
        "freshness_counts": counts,
        "sources": entries,
        "risks": [risk_view(risk) for risk in company.risks],
    }
