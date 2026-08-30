"""Truth-preserving activation funnel over canonical measurement evidence.

The funnel reports evidence coverage separately from customer progression. It refuses
to publish a conversion/drop-off rate when instrumentation semantics are partial or
unknown, preventing measurement debt from becoming a fabricated customer behavior.
"""
from __future__ import annotations

from analytics_measurement import (
    OBSERVABLE,
    PARTIAL,
    UNKNOWN,
    account_milestones,
    event_taxonomy,
)

FUNNEL_VERSION = "activation-funnel-v1"

# These are measurement stages, not new product/domain states.
_STAGE_MAP = (
    ("signup", "signup"),
    ("profile_completion", "profile_completion"),
    ("market_readiness", "market_readiness"),
    ("first_shortlist", "first_shortlist"),
    ("useful_opportunity_viewed", "opportunity_viewed"),
    ("evaluation_activation", "evaluation_activation"),
)


def _account_ids(conn):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='accounts'"
    ).fetchone()
    if not exists:
        return []
    columns = {row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    if "account_id" not in columns:
        return []
    return [str(row[0]) for row in conn.execute("SELECT account_id FROM accounts ORDER BY account_id").fetchall()]


def activation_funnel(conn):
    """Return activation evidence without inventing conversion or drop-off.

    `progression_rate` is emitted only when the current stage and its previous stage
    both have fully observable measurement contracts and zero UNKNOWN accounts.
    Otherwise it is `None` with an explicit blocker.
    """
    accounts = _account_ids(conn)
    registry = event_taxonomy()
    snapshots = {account_id: account_milestones(conn, account_id) for account_id in accounts}
    stages = []
    previous = None

    for public_name, measurement_name in _STAGE_MAP:
        contract = registry[measurement_name]
        qualities = [snapshots[a][measurement_name]["quality"] for a in accounts]
        observed = sum(1 for quality in qualities if quality == OBSERVABLE)
        partial = sum(1 for quality in qualities if quality == PARTIAL)
        unknown = sum(1 for quality in qualities if quality == UNKNOWN)
        eligible = contract["status"] == OBSERVABLE and unknown == 0 and partial == 0

        stage = {
            "stage": public_name,
            "measurement": measurement_name,
            "contract_status": contract["status"],
            "population_accounts": len(accounts),
            "observed_accounts": observed,
            "partial_evidence_accounts": partial,
            "unknown_accounts": unknown,
            "measurement_complete": eligible,
            "progression_rate": None,
            "dropoff_rate": None,
            "rate_blocker": None,
        }

        if previous is None:
            stage["rate_blocker"] = "first_stage_has_no_previous_stage"
        elif not previous["measurement_complete"] or not eligible:
            stage["rate_blocker"] = "incomplete_measurement_contract_or_unknown_population"
        elif previous["observed_accounts"] == 0:
            stage["rate_blocker"] = "zero_observed_previous_stage_denominator"
        else:
            progression = observed / previous["observed_accounts"]
            # A funnel stage should never exceed its previous stage under a valid
            # monotonic contract. If it does, expose the inconsistency rather than
            # silently clipping or claiming a negative drop-off.
            if progression > 1:
                stage["rate_blocker"] = "non_monotonic_event_history"
            else:
                stage["progression_rate"] = progression
                stage["dropoff_rate"] = 1 - progression
        stages.append(stage)
        previous = stage

    return {
        "funnel_version": FUNNEL_VERSION,
        "population_accounts": len(accounts),
        "stages": stages,
        "interpretation": (
            "Rates are withheld whenever instrumentation is partial/unknown. "
            "UNKNOWN is measurement debt, not customer abandonment."
        ),
    }
