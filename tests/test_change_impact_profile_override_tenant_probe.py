"""Change-impact failing-before probe for account/profile composition safety.

Evidence-only. This test does not choose the repair mechanism. The invariant is that
an explicit preloaded profile supplied to the account-scoped classifier must never
be evaluated under a different account_id.
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
    """A caller-provided profile must not silently become another tenant's input.

    Safe implementations may reject before evaluation or discard/reload a profile
    whose embedded account_id disagrees with the account_id argument. They must not
    evaluate the mismatched supplied profile.
    """

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

    try:
        funnel_integration.persist_and_classify(
            object(),
            {"source": "TEST", "external_id": "cross-tenant-profile"},
            True,
            account_id="account-b",
            profile={"account_id": "account-a", "marker": "wrong-tenant"},
        )
    except Exception:
        # Fail-closed rejection is an acceptable owner repair.
        pass

    assert all(
        profile.get("account_id") == "account-b" for profile in evaluated_profiles
    ), "mismatched caller-supplied tenant profile reached decision evaluation"

    if recorded:
        assert evaluated_profiles, "decision was recorded without a validated evaluation"
        assert all(profile.get("account_id") == "account-b" for profile in evaluated_profiles)
