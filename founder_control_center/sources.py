from __future__ import annotations

from .models import CompanyManifest, Evidence, TruthState


LIVE_KINDS = {"live_adapter", "factory_feed", "business_metric_feed", "operational_metric_feed"}


def _entry(label: str, category: str, evidence: Evidence | None, claimed_state: str | None = None) -> dict:
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
        entries.append(_entry(f"Risk: {risk.title}", "risk", risk.evidence, risk.severity))
    return entries


def source_summary(company: CompanyManifest) -> dict:
    entries = source_inventory(company)
    counts = {state.value: 0 for state in TruthState}
    for item in entries:
        counts[item["freshness"]] = counts.get(item["freshness"], 0) + 1
    connected = [item for item in entries if item["kind"] in LIVE_KINDS]
    fresh_connected = [item for item in connected if item["freshness"] == TruthState.GREEN.value]
    return {
        "company_id": company.id,
        "total": len(entries),
        "connected_source_count": len(connected),
        "fresh_live_source_count": len(fresh_connected),
        "live_source_count": len(fresh_connected),
        "freshness_counts": counts,
        "sources": entries,
    }
