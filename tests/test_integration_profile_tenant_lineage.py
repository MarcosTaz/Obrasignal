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


def test_mismatched_preload_fingerprints_authoritative_profile_only(monkeypatch):
    wrong_profile = {
        "account_id": "account-a",
        "marker": "wrong-tenant",
        "keywords": ["private-a"],
    }
    authoritative_profile = {
        "account_id": "account-b",
        "marker": "reloaded",
        "keywords": ["authoritative-b"],
    }
    evaluated_profiles = []
    captured = {}

    monkeypatch.setattr(
        funnel_integration,
        "load_profile",
        lambda account_id: dict(authoritative_profile),
    )
    monkeypatch.setattr(
        funnel_integration,
        "evaluate_row",
        lambda item, profile: evaluated_profiles.append(dict(profile)) or _evaluation(),
    )

    def capture(*args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(funnel_integration, "record_decision", capture)

    funnel_integration.persist_and_classify(
        object(),
        {"source": "TEST", "external_id": "tenant-lineage"},
        True,
        account_id="account-b",
        profile=wrong_profile,
    )

    assert evaluated_profiles == [authoritative_profile]
    assert captured["account_id"] == "account-b"

    profile_lineage = captured["features"]["lineage"]["profile"]
    assert profile_lineage["fingerprint"] == data_lineage.canonical_fingerprint(
        authoritative_profile
    )
    assert profile_lineage["fingerprint"] != data_lineage.canonical_fingerprint(
        wrong_profile
    )
    assert profile_lineage["reconstruction"] == "FINGERPRINT_ONLY"
    assert profile_lineage["privacy_class"] == "HASHED_DERIVATION_METADATA"
