from __future__ import annotations

from dataclasses import dataclass

from .models import CompanyManifest, TruthState


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


def rank_company(company: CompanyManifest) -> RankResult:
    """Evidence-weighted attention ranking. Score is guidance, never objective truth."""
    score = 25.0
    reasons: list[str] = []
    known = 0
    total = 8
    if company.status == "ACTIVE":
        score += 8; reasons.append("active portfolio item"); known += 1
    if company.stage not in ("UNKNOWN", "research / validation", "venture discovery / thesis validation"):
        score += 9; reasons.append("beyond pure research"); known += 1
    if company.wait not in ("NONE", "UNKNOWN"):
        score += 5; reasons.append("material blocker deserves attention"); known += 1
    if company.repository.full_name:
        score += 5; reasons.append("repository source identifiable"); known += 1
    if company.application.health == TruthState.DEGRADED:
        score += 15; reasons.append("application health degraded"); known += 1
    elif company.application.health == TruthState.GREEN:
        known += 1
    if _known(company.revenue):
        score += 12; reasons.append("revenue evidence available"); known += 1
    if _known(company.pipeline):
        score += 8; reasons.append("pipeline evidence available"); known += 1
    if company.risks:
        if any(r.severity in ("CRITICAL", "HIGH") for r in company.risks):
            score += 10; reasons.append("high-severity risk")
        known += 1
    uncertainty = round(1 - min(1, known / total), 2)
    score = round(min(100.0, max(0.0, score * (1 - uncertainty * 0.35))), 1)
    if uncertainty >= 0.5:
        reasons.append("ranking heavily discounted because evidence is incomplete")
    return RankResult(company.id, score, uncertainty, reasons[:5])


def rank_portfolio(companies: list[CompanyManifest]) -> list[RankResult]:
    return sorted((rank_company(c) for c in companies), key=lambda x: x.score, reverse=True)


def highest_value_actions(companies: list[CompanyManifest], limit: int = 8) -> list[dict]:
    """Portfolio-level action queue derived from current manifests and ranking evidence."""
    ranks = {r.company_id: r for r in rank_portfolio(companies)}
    items: list[dict] = []
    for company in companies:
        rank = ranks[company.id]
        severity = next((r.severity for r in company.risks if r.severity in ("CRITICAL", "HIGH")), None)
        if company.application.health == TruthState.DEGRADED:
            action, boundary, urgency = "Diagnose degraded application health", "GREEN", "critical"
        elif company.repository.full_name and company.repository.commit is None:
            action, boundary, urgency = "Refresh repository truth", "GREEN", "high"
        elif company.stage in ("research / validation", "venture discovery / thesis validation"):
            action, boundary, urgency = "Close the highest-value evidence gap before building", "GREEN", "medium"
        else:
            action, boundary = company.active or "Resolve current ACTIVE", "GREEN"
            urgency = "high" if severity else "medium"
        items.append({"company_id": company.id, "company_name": company.name, "action": action, "urgency": urgency, "expected_value": rank.score, "uncertainty": rank.uncertainty, "owner_boundary": boundary, "why": rank.reasons[0] if rank.reasons else "Insufficient evidence; prioritize truth acquisition"})
    return sorted(items, key=lambda x: (x["urgency"] == "critical", x["expected_value"]), reverse=True)[:limit]
