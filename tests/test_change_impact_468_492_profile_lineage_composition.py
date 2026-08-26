import data_lineage
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


def test_cross_account_override_fingerprints_authoritative_reloaded_profile(monkeypatch):
    supplied_a = {"account_id": "account-a", "marker": "discarded-a"}
    authoritative_b = {"account_id": "account-b", "marker": "authoritative-b"}
    evaluated = []
    recorded = {}

    monkeypatch.setattr(
        funnel_integration,
        "load_profile",
        lambda account_id: dict(authoritative_b) if account_id == "account-b" else (_ for _ in ()).throw(AssertionError(account_id)),
    )
    monkeypatch.setattr(
        funnel_integration,
        "evaluate_row",
        lambda item, profile: evaluated.append(dict(profile)) or _evaluation(),
    )

    def capture(*args, **kwargs):
        recorded.update(kwargs)

    monkeypatch.setattr(funnel_integration, "record_decision", capture)

    funnel_integration.persist_and_classify(
        object(),
        {"source": "TEST", "external_id": "same-opportunity"},
        True,
        account_id="account-b",
        profile=supplied_a,
    )

    assert evaluated == [authoritative_b]
    assert recorded["account_id"] == "account-b"
    lineage = recorded["features"]["lineage"]["profile"]
    assert lineage["fingerprint"] == data_lineage.canonical_fingerprint(authoritative_b)
    assert lineage["fingerprint"] != data_lineage.canonical_fingerprint(supplied_a)


def test_same_account_profile_fingerprint_matches_actual_evaluated_input(monkeypatch):
    profile_a = {"account_id": "account-a", "marker": "snapshot-a"}
    evaluated = []
    recorded = {}

    monkeypatch.setattr(
        funnel_integration,
        "load_profile",
        lambda account_id: (_ for _ in ()).throw(AssertionError("same-account explicit profile should not reload")),
    )
    monkeypatch.setattr(
        funnel_integration,
        "evaluate_row",
        lambda item, profile: evaluated.append(dict(profile)) or _evaluation(),
    )
    monkeypatch.setattr(
        funnel_integration,
        "record_decision",
        lambda *args, **kwargs: recorded.update(kwargs),
    )

    funnel_integration.persist_and_classify(
        object(),
        {"source": "TEST", "external_id": "same-opportunity"},
        True,
        account_id="account-a",
        profile=profile_a,
    )

    assert evaluated == [profile_a]
    assert recorded["account_id"] == "account-a"
    assert recorded["features"]["lineage"]["profile"]["fingerprint"] == data_lineage.canonical_fingerprint(profile_a)


def test_missing_profile_account_identity_is_not_accepted_as_account_b_authority(monkeypatch):
    supplied_unknown = {"marker": "missing-account-id"}
    authoritative_b = {"account_id": "account-b", "marker": "authoritative-b"}
    recorded = {}

    monkeypatch.setattr(funnel_integration, "load_profile", lambda account_id: dict(authoritative_b))
    monkeypatch.setattr(funnel_integration, "evaluate_row", lambda item, profile: _evaluation())
    monkeypatch.setattr(
        funnel_integration,
        "record_decision",
        lambda *args, **kwargs: recorded.update(kwargs),
    )

    funnel_integration.persist_and_classify(
        object(),
        {"source": "TEST", "external_id": "missing-account"},
        True,
        account_id="account-b",
        profile=supplied_unknown,
    )

    fingerprint = recorded["features"]["lineage"]["profile"]["fingerprint"]
    assert fingerprint == data_lineage.canonical_fingerprint(authoritative_b)
    assert fingerprint != data_lineage.canonical_fingerprint(supplied_unknown)
