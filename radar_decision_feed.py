"""Decision-aware radar feed helpers."""
from __future__ import annotations

from decision_log import latest_decision
from radar_decision_summary import summarize_decision


def _layers(decision: dict | None) -> list[dict]:
    features = (decision or {}).get("features") or {}
    layers: list[dict] = []

    profile_score = features.get("profile_score")
    if profile_score is not None:
        layers.append({
            "key": "profile",
            "label": "Perfil",
            "kind": "score",
            "score": profile_score,
            "detail": "compatibilidade geral com o perfil da empresa",
        })

    lot_score = features.get("lot_score")
    if lot_score is not None:
        layers.append({
            "key": "lot",
            "label": "Lote",
            "kind": "score",
            "score": lot_score,
            "detail": f"lote {features.get('lot_id') or 'não identificado'}",
        })

    geography = features.get("geography") or {}
    if geography:
        layers.append({
            "key": "geography",
            "label": "Geografia",
            "kind": "score",
            "score": geography.get("score"),
            "detail": geography.get("reason") or "localização sem detalhe",
        })

    capability = features.get("capability_evidence") or {}
    if capability:
        detail = capability.get("reason") or "sem evidência explícita"
        matched = capability.get("matched_services") or []
        if matched:
            detail += ": " + ", ".join(str(value) for value in matched[:3])
        layers.append({
            "key": "capability",
            "label": "Capacidade",
            "kind": "evidence",
            "score": None,
            "evidence_count": capability.get("evidence_count", 0),
            "detail": detail,
        })

    economics = features.get("economic_fit") or {}
    if economics:
        layers.append({
            "key": "economic_fit",
            "label": "Economic Fit",
            "kind": "score",
            "score": economics.get("score"),
            "status": economics.get("status") or "UNKNOWN",
            "detail": economics.get("reason") or economics.get("status") or "sem detalhe",
        })

    blockers = features.get("hard_capability_blockers") or []
    if blockers:
        layers.append({
            "key": "blockers",
            "label": "Bloqueios",
            "kind": "blocker",
            "score": None,
            "evidence_count": len(blockers),
            "detail": "; ".join(str(item) for item in blockers),
        })

    return layers


def enrich_rows(conn, rows):
    enriched = []
    for row in rows:
        item = dict(row)
        decision = latest_decision(conn, item.get("source"), item.get("external_id"))
        summary = summarize_decision(decision)
        summary["layers"] = _layers(decision)
        item["decision_summary"] = summary
        enriched.append(item)
    return enriched
