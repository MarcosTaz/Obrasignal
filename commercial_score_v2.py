"""Explainable commercial Opportunity Score v2.

Uses structured procurement fields when available, while remaining backward
compatible with the existing tender dictionaries.
"""
from datetime import datetime, timezone

RULE_VERSION = "commercial-v2"

WORKS_CPVS = ("45",)
METAL_CPVS = ("45223", "45262", "45261", "45262", "45262")


def _text(*values):
    return " ".join(str(v or "") for v in values).lower()


def _deadline_days(value):
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    for parser in (
        lambda: datetime.fromisoformat(s),
        lambda: datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc),
        lambda: datetime.strptime(s[:8], "%Y%m%d").replace(tzinfo=timezone.utc),
    ):
        try:
            dt = parser()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (dt.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds() / 86400
        except Exception:
            pass
    return None


def score_v2(item):
    """Return score and a component-by-component explanation."""
    title = item.get("title")
    description = item.get("description")
    buyer = item.get("buyer")
    cpv = str(item.get("cpv") or "")
    text = _text(title, description)

    components = {}
    reasons = []

    # 0-35: structured CPV/nature fit.
    if any(code.strip().startswith(WORKS_CPVS) for code in cpv.split("|")):
        components["cpv_fit"] = 35
        reasons.append("CPV de obras")
    elif any(code.strip().startswith("44") for code in cpv.split("|")):
        components["cpv_fit"] = 25
        reasons.append("CPV de materiais/construção")
    else:
        components["cpv_fit"] = 8

    # 0-20: target capability signals. Text is supplementary, never the only gate.
    capability_terms = (
        "metalomecânica", "metalomecanica", "estrutura metálica", "estruturas metálicas",
        "serralharia", "steel", "aço", "aco", "metal", "cobertura", "fachada",
        "armazém", "armazem", "warehouse", "montagem", "empreitada"
    )
    hits = [term for term in capability_terms if term in text]
    components["capability_fit"] = min(20, 6 * len(dict.fromkeys(hits))) if hits else 0
    if hits:
        reasons.append("atividade compatível: " + ", ".join(dict.fromkeys(hits)[:3]))

    # 0-15: deadline urgency, with expired notices receiving zero.
    days = _deadline_days(item.get("deadline"))
    if days is None:
        components["deadline"] = 5
    elif days < 0:
        components["deadline"] = 0
        reasons.append("prazo terminado")
    elif days <= 3:
        components["deadline"] = 15
        reasons.append("prazo muito próximo")
    elif days <= 14:
        components["deadline"] = 12
        reasons.append("prazo curto")
    elif days <= 45:
        components["deadline"] = 8
    else:
        components["deadline"] = 4

    # 0-15: size fit. Keep unknown values neutral rather than inventing a value.
    value = item.get("value_numeric")
    try:
        value = float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        value = None
    if value is None:
        components["size_fit"] = 7
    elif value <= 250_000:
        components["size_fit"] = 15
        reasons.append("valor compatível com operação pequena/média")
    elif value <= 1_000_000:
        components["size_fit"] = 11
    elif value <= 5_000_000:
        components["size_fit"] = 6
    else:
        components["size_fit"] = 2
        reasons.append("valor elevado")

    # 0-10: procedure/accessibility. Prefer structured procedure_type when present.
    procedure = _text(item.get("procedure_type"), item.get("notice_type"), buyer)
    if any(k in procedure for k in ("open", "aberto", "open procedure")):
        components["access"] = 10
    elif any(k in procedure for k in ("restricted", "negociat", "dialogue")):
        components["access"] = 6
        reasons.append("procedimento com acesso mais exigente")
    else:
        components["access"] = 7

    # Hard negative for clearly intellectual-only procurement.
    if any(k in text for k in ("architecture services", "serviços de arquitetura", "servicos de arquitetura", "consultoria", "fiscalização", "fiscalizacao")) and not any(k in text for k in ("obra", "works", "construction", "empreitada", "execução", "execucao")):
        components["capability_fit"] = 0
        components["access"] = min(components["access"], 3)
        reasons.append("atividade predominantemente intelectual")

    score = max(0, min(100, sum(components.values())))
    if score >= 80:
        priority = "PRIORIDADE MÁXIMA"
    elif score >= 65:
        priority = "ALTA PRIORIDADE"
    elif score >= 50:
        priority = "BOA OPORTUNIDADE"
    else:
        priority = "BAIXA PRIORIDADE"

    return {
        "score": score,
        "priority_label": priority,
        "components": components,
        "reasons": reasons[:6],
        "rule_version": RULE_VERSION,
        "deadline_days": days,
    }
