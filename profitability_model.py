"""Conservative economics for procurement opportunities.

This module deliberately estimates economic potential rather than pretending to
predict net profit. Tender value is not guaranteed revenue, so outputs are
ranges with an explicit confidence level.
"""

RULE_VERSION = "profitability-v1"


def _num(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def estimate_profitability(value, profile=None):
    """Return an economic attractiveness estimate for a tender/lot.

    Profile knobs are optional and intentionally simple:
      target_margin: desired gross margin as decimal (default 0.20)
      delivery_cost_ratio: estimated direct delivery cost / contract value
      risk_buffer: contingency / contract value

    If value is missing, the model returns UNKNOWN rather than inventing a
    monetary result.
    """
    profile = profile or {}
    amount = _num(value)
    if amount is None or amount <= 0:
        return {
            "status": "UNKNOWN",
            "confidence": 0,
            "estimated_revenue": None,
            "estimated_cost": None,
            "estimated_gross_profit": None,
            "estimated_margin": None,
            "reason": "valor do contrato inexistente ou inválido",
            "rule_version": RULE_VERSION,
        }

    margin = _num(profile.get("target_margin"))
    cost_ratio = _num(profile.get("delivery_cost_ratio"))
    risk = _num(profile.get("risk_buffer"))
    margin = 0.20 if margin is None else max(0.0, min(0.80, margin))
    cost_ratio = (1.0 - margin) if cost_ratio is None else max(0.0, min(1.0, cost_ratio))
    risk = 0.05 if risk is None else max(0.0, min(0.50, risk))

    estimated_cost = amount * (cost_ratio + risk)
    estimated_profit = amount - estimated_cost
    # Round the comparison value so boundary cases such as exactly 15% are
    # classified deterministically despite binary floating-point representation.
    estimated_margin = round(estimated_profit / amount, 4)

    # Status is an economic attractiveness band; target_margin remains the
    # user's desired hurdle and is exposed in the explanation.
    if estimated_margin >= 0.15:
        status = "ATTRACTIVE"
    elif estimated_margin >= 0.10:
        status = "POSSIBLE"
    else:
        status = "THIN"

    confidence = 45
    if profile.get("delivery_cost_ratio") is not None:
        confidence += 20
    if profile.get("target_margin") is not None:
        confidence += 15
    if profile.get("risk_buffer") is not None:
        confidence += 10
    confidence = min(90, confidence)

    gap = estimated_margin - margin
    return {
        "status": status,
        "confidence": confidence,
        "estimated_revenue": round(amount, 2),
        "estimated_cost": round(estimated_cost, 2),
        "estimated_gross_profit": round(estimated_profit, 2),
        "estimated_margin": estimated_margin,
        "assumptions": {
            "target_margin": margin,
            "delivery_cost_ratio": cost_ratio,
            "risk_buffer": risk,
        },
        "reason": (
            f"margem estimada={estimated_margin:.1%}; "
            f"meta={margin:.1%}; desvio={gap:+.1%}; confiança={confidence}%"
        ),
        "rule_version": RULE_VERSION,
    }
