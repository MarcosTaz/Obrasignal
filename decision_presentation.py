"""Presentation helpers for auditable opportunity decisions."""
from __future__ import annotations


def _status_text(decision: dict | None) -> str:
    if not decision:
        return "SEM DECISÃO"
    return str(decision.get("decision") or "SEM DECISÃO")


def _feature_lines(features: dict | None) -> list[dict]:
    features = features or {}
    lines: list[dict] = []

    profile_score = features.get("profile_score")
    if profile_score is not None:
        lines.append({"label": "Perfil da empresa", "value": f"{profile_score}/100", "detail": "compatibilidade geral com o perfil"})

    lot_score = features.get("lot_score")
    if lot_score is not None:
        lot_id = features.get("lot_id") or "não identificado"
        lines.append({"label": "Lote", "value": f"{lot_score}/100", "detail": f"lote {lot_id}"})

    geography = features.get("geography") or {}
    if geography:
        geo_score = geography.get("score")
        geo_reason = geography.get("reason") or "localização sem detalhe"
        value = f"{geo_score}/5" if geo_score is not None else "—"
        lines.append({"label": "Geografia", "value": value, "detail": geo_reason})

    capability = features.get("capability_evidence") or {}
    if capability:
        evidence_count = capability.get("evidence_count", 0)
        detail = capability.get("reason") or "sem evidência explícita"
        if capability.get("matched_services"):
            detail += ": " + ", ".join(capability["matched_services"][:3])
        lines.append({"label": "Capacidade", "value": f"{evidence_count} evidência(s)", "detail": detail})

    economics = features.get("economic_fit") or {}
    if economics:
        score = economics.get("score")
        status = economics.get("status") or "UNKNOWN"
        value = f"{score}/100" if score is not None else status
        lines.append({"label": "Economic Fit", "value": value, "detail": economics.get("reason") or status})

    blockers = features.get("hard_capability_blockers") or []
    if blockers:
        lines.append({"label": "Bloqueios", "value": str(len(blockers)), "detail": "; ".join(str(item) for item in blockers)})

    return lines


def present_decision(decision: dict | None) -> dict:
    """Convert persisted decision data into a stable UI payload."""
    decision = decision or {}
    features = decision.get("features") or {}
    return {
        "status": _status_text(decision),
        "reason": decision.get("reason") or "Não existe uma razão registada.",
        "score": decision.get("score"),
        "confidence": decision.get("confidence"),
        "rule_version": decision.get("rule_version"),
        "decided_at": decision.get("decided_at"),
        "lines": _feature_lines(features),
    }
