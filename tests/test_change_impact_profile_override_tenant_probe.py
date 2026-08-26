"""Passing-after composition probe for account/profile tenant safety.

This test preserves the exact #493 failing-before invariant on the repaired
Performance owner successor. A caller-provided profile must never be evaluated
under a different account_id.
"""

import funnel_integration


def _evaluation():
    return {
        "lot_score": 1,
        "match": True,
        "lot_id": "lot",
        "geography": {"score": 1, "reason": "ok"},
        "decision": "REVIEW",
        "reason": "test",
        "profile_score": 1,
        "commercial": {},
        "economic_fit": {},
        "capability": {},
        "capability_evidence": [],
        "cpv_evidence": [],
        "hard_capability_blockers": [],
        "explanation": {},
    }


def test_explicit_profile_cannot_cross_account_boundary(monkeypatch):
    evaluated_profiles = []
    recorded = []

    monkeypatch.setattr(
        funnel_integration,
        "load_profile",
        lambda account_id: {"account_id": account_id, "marker": "reloaded"},
    )

    def evaluate_row(item, profile):
        evaluated_profiles.append(dict(profile))
        return _evaluation()

    monkeypatch.setattr(funnel_integration, "evaluate_row", evaluate_row)
    monkeypatch.setattr(
        funnel_integration,
        "record_decision",
        lambda *args, **kwargs: recorded.append((args, kwargs)),
    )

    funnel_integration.persist_and_classify(
        object(),
        {"source": "TEST", "external_id": "cross-tenant-profile"},
        True,
        account_id="account-b",
        profile={"account_id": "account-a", "marker": "wrong-tenant"},
    )

    assert evaluated_profiles == [{"account_id": "account-b", "marker": "reloaded"}]
    assert recorded, "repaired classification should still persist the validated decision"
