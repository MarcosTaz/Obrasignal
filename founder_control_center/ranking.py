from __future__ import annotations

from dataclasses import dataclass

from .models import CompanyManifest, TruthState
from .sources import risk_current_state


@dataclass
class RankResult:
    company_id: str
    score: float
    uncertainty: float
    reasons: list[str]

    def to_dict(self) -> dict:
        return {"company_id": self.company_id, "score": self.score, "uncertainty": self.uncertainty, "reasons": self.reasons}


def _known(metric) -> bool:
    return getattr(metric, "state", TruthState.UNKNOWN) not in (TruthState.UNKNOWN, TruthState.STALE)


def _factory_feed_states(company: CompanyManifest) -> list[TruthState]:
    return [
        factory.freshness
        for factory in company.factories
        if factory.evidence is not None and factory.evidence.kind == "factory_feed"
    ]


def _high_risk_states(company: CompanyManifest) -> list[TruthState]:
    return [
        risk_current_state(risk)
        for risk in company.risks
        if str(risk.severity).upper() in {"CRITICAL", "HIGH"}
    ]


def rank_company(company: CompanyManifest) -> RankResult:
    """Evidence-weighted attention ranking. Score is guidance, never objective truth."""
    score = 20.0
    reasons: list[str] = []
    known = 0
    total = 12

    if company.status == "ACTIVE":
        score += 6
        reasons.append("active portfolio item")
        known += 1

    if company.stage not in ("UNKNOWN", "research / validation", "venture discovery / thesis validation"):
        score += 8
        reasons.append("beyond pure research")
        known += 1

    if company.wait not in ("NONE", "UNKNOWN"):
        score += 6
        reasons.append("material blocker deserves attention")
        known += 1

    if company.repository.full_name:
        score += 3
        known += 1
        if company.repository.ci == TruthState.DEGRADED:
            score += 18
            reasons.append("repository CI degraded")
        elif company.repository.ci == TruthState.GREEN:
            reasons.append("repository CI proven green")
        elif company.repository.ci == TruthState.STALE:
            score += 8
            reasons.append("repository CI evidence stale")
    if company.repository.ci not in (TruthState.UNKNOWN, TruthState.STALE):
        known += 1

    if company.application.deployment == TruthState.DEGRADED:
        score += 20
        reasons.append("deployment degraded")
        known += 1
    elif company.application.deployment == TruthState.GREEN:
        known += 1
    elif company.application.deployment == TruthState.STALE:
        score += 8
        reasons.append("deployment evidence stale")

    if company.application.health == TruthState.DEGRADED:
        score += 20
        reasons.append("application health degraded")
        known += 1
    elif company.application.health == TruthState.GREEN:
        known += 1
    elif company.application.health == TruthState.STALE:
        score += 8
        reasons.append("application health evidence stale")

    if _known(company.revenue):
        score += 12
        reasons.append("revenue evidence available")
        known += 1

    if _known(company.pipeline):
        score += 8
        reasons.append("pipeline evidence available")
        known += 1

    high_risk_states = _high_risk_states(company)
    if any(state == TruthState.GREEN for state in high_risk_states):
        score += 10
        known += 1
        reasons.append("fresh high-severity risk evidence")
    elif any(state == TruthState.STALE for state in high_risk_states):
        score += 8
        reasons.append("high-severity risk evidence stale")

    factory_states = _factory_feed_states(company)
    if any(state == TruthState.STALE for state in factory_states):
        score += 10
        reasons.append("Factory feed evidence stale")
    elif any(state == TruthState.GREEN for state in factory_states):
        known += 1
        reasons.append("live Factory feed evidence available")
    elif any(state == TruthState.DEGRADED for state in factory_states):
        score += 10
        known += 1
        reasons.append("Factory feed degraded")

    if company.data_freshness == TruthState.DEGRADED:
        score += 6
        reasons.append("portfolio data freshness degraded")
        known += 1
    elif company.data_freshness == TruthState.GREEN:
        known += 1
    elif company.data_freshness == TruthState.STALE:
        score += 10
        reasons.append("portfolio data freshness stale")

    uncertainty = round(1 - min(1, known / total), 2)
    score = round(min(100.0, max(0.0, score * (1 - uncertainty * 0.35))), 1)
    if uncertainty >= 0.5:
        reasons.append("ranking heavily discounted because evidence is incomplete")
    return RankResult(company.id, score, uncertainty, reasons[:6])


def rank_portfolio(companies: list[CompanyManifest]) -> list[RankResult]:
    return sorted((rank_company(c) for c in companies), key=lambda x: x.score, reverse=True)


def highest_value_actions(companies: list[CompanyManifest], limit: int = 8) -> list[dict]:
    """Portfolio-level action queue derived from current manifests and ranking evidence."""
    ranks = {r.company_id: r for r in rank_portfolio(companies)}
    items: list[dict] = []
    for company in companies:
        rank = ranks[company.id]
        high_risk_states = _high_risk_states(company)
        fresh_high_risk = any(state == TruthState.GREEN for state in high_risk_states)
        stale_high_risk = any(state == TruthState.STALE for state in high_risk_states)
        factory_states = _factory_feed_states(company)

        if company.application.health == TruthState.DEGRADED:
            action, boundary, urgency = "Diagnose degraded application health", "GREEN", "critical"
        elif company.application.deployment == TruthState.DEGRADED:
            action, boundary, urgency = "Diagnose degraded deployment before any release action", "GREEN", "critical"
        elif company.repository.ci == TruthState.DEGRADED:
            action, boundary, urgency = "Diagnose failing repository CI", "GREEN", "critical"
        elif stale_high_risk:
            action, boundary, urgency = "Refresh stale high-severity risk evidence before deciding", "GREEN", "high"
        elif any(state == TruthState.STALE for state in factory_states):
            action, boundary, urgency = "Refresh stale Factory feed before portfolio decisions", "GREEN", "high"
        elif company.data_freshness == TruthState.STALE:
            action, boundary, urgency = "Refresh stale canonical sources before deciding", "GREEN", "high"
        elif company.repository.full_name and company.repository.commit is None:
            action, boundary, urgency = "Refresh repository truth", "GREEN", "high"
        elif company.stage in ("research / validation", "venture discovery / thesis validation"):
            action, boundary, urgency = "Close the highest-value evidence gap before building", "GREEN", "medium"
        else:
            action, boundary = company.active or "Resolve current ACTIVE", "GREEN"
            urgency = "high" if fresh_high_risk else "medium"

        items.append({
            "company_id": company.id,
            "company_name": company.name,
            "action": action,
            "urgency": urgency,
            "expected_value": rank.score,
            "uncertainty": rank.uncertainty,
            "owner_boundary": boundary,
            "why": rank.reasons[0] if rank.reasons else "Insufficient evidence; prioritize truth acquisition",
        })

    urgency_weight = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    return sorted(items, key=lambda x: (urgency_weight.get(x["urgency"], 0), x["expected_value"]), reverse=True)[:limit]
