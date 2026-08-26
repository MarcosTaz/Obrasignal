"""Change Impact passing-after retest for repaired #468 tenant/profile binding.

Historical #493 remains immutable failing-before evidence. This test reuses the same
semantic invariant against repaired #468: a caller-supplied profile for account A
must never be evaluated under account B authority.
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


def test_repaired_classifier_discards_cross_account_profile_and_evaluates_authoritative_account(monkeypatch):
    loads = []
    evaluated_profiles = []
    recorded_accounts = []

    def load_profile(account_id):
        loads.append(account_id)
        return {"account_id": account_id, "marker": "authoritative-b"}

    monkeypatch.setattr(funnel_integration, "load_profile", load_profile)
    monkeypatch.setattr(
        funnel_integration,
        "evaluate_row",
        lambda item, profile: evaluated_profiles.append(dict(profile)) or _evaluation(),
    )
    monkeypatch.setattr(
        funnel_integration,
        "record_decision",
        lambda *args, **kwargs: recorded_accounts.append(kwargs.get("account_id")),
    )

    funnel_integration.persist_and_classify(
        object(),
        {"source": "TEST", "external_id": "cross-tenant-profile"},
        True,
        account_id="account-b",
        profile={"account_id": "account-a", "marker": "discard-me"},
    )

    assert loads == ["account-b"]
    assert evaluated_profiles == [
        {"account_id": "account-b", "marker": "authoritative-b"}
    ]
    assert recorded_accounts == ["account-b"]
