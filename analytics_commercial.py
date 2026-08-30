"""Commercial funnel contract consuming GTM/Billing evidence without owning it."""
from __future__ import annotations

COMMERCIAL_VERSION = "commercial-funnel-v1"

STAGES = (
    "outreach",
    "reply",
    "interest",
    "pilot",
    "wtp",
    "evaluation",
    "paid",
    "retained",
)

_ALLOWED_QUALITY = {"OBSERVABLE", "PARTIAL", "UNKNOWN"}


def evidence_point(*, quality, count=None, source_owner, observed_at=None, note=None):
    quality = str(quality or "").upper().strip()
    if quality not in _ALLOWED_QUALITY:
        raise ValueError("invalid_commercial_evidence_quality")
    if not str(source_owner or "").strip():
        raise ValueError("commercial_source_owner_required")
    if quality == "OBSERVABLE":
        if count is None or isinstance(count, bool) or int(count) < 0:
            raise ValueError("observable_commercial_evidence_requires_nonnegative_count")
        count = int(count)
    elif count is not None:
        # A numeric count attached to partial/unknown evidence is too easy to reuse
        # as a real funnel number. Keep it absent until the owner proves coverage.
        raise ValueError("partial_or_unknown_commercial_evidence_cannot_publish_count")
    return {
        "quality": quality,
        "count": count,
        "source_owner": str(source_owner).strip(),
        "observed_at": observed_at,
        "note": note,
    }


def commercial_funnel(evidence):
    """Build a funnel where silence/missing stages can never become rejection/zero."""
    evidence = dict(evidence or {})
    unknown_stage_names = sorted(set(evidence) - set(STAGES))
    if unknown_stage_names:
        raise ValueError({"unknown_commercial_stages": unknown_stage_names})

    stages = []
    previous = None
    for name in STAGES:
        point = evidence.get(name) or {
            "quality": "UNKNOWN",
            "count": None,
            "source_owner": "UNPROVIDED",
            "observed_at": None,
            "note": "missing owner evidence",
        }
        quality = point.get("quality")
        count = point.get("count")
        if quality not in _ALLOWED_QUALITY:
            raise ValueError(f"invalid_commercial_evidence_quality:{name}")
        if quality == "OBSERVABLE" and (count is None or isinstance(count, bool) or int(count) < 0):
            raise ValueError(f"observable_stage_requires_count:{name}")
        if quality != "OBSERVABLE" and count is not None:
            raise ValueError(f"unproven_stage_cannot_publish_count:{name}")

        stage = {
            "stage": name,
            "quality": quality,
            "count": int(count) if count is not None else None,
            "source_owner": point.get("source_owner"),
            "observed_at": point.get("observed_at"),
            "progression_rate": None,
            "dropoff_rate": None,
            "rate_blocker": None,
        }

        if previous is None:
            stage["rate_blocker"] = "first_stage_has_no_previous_stage"
        elif previous["quality"] != "OBSERVABLE" or quality != "OBSERVABLE":
            stage["rate_blocker"] = "missing_or_partial_owner_evidence"
        elif previous["count"] == 0:
            stage["rate_blocker"] = "zero_previous_stage_denominator"
        elif stage["count"] > previous["count"]:
            stage["rate_blocker"] = "non_monotonic_cross_owner_evidence"
        else:
            rate = stage["count"] / previous["count"]
            stage["progression_rate"] = rate
            stage["dropoff_rate"] = 1 - rate

        stages.append(stage)
        previous = stage

    return {
        "schema_version": COMMERCIAL_VERSION,
        "stages": stages,
        "interpretation": (
            "Only owner-proven OBSERVABLE counts participate in rates. Missing reply/interest/WTP evidence "
            "is UNKNOWN and is never interpreted as rejection, churn, or zero demand."
        ),
    }
