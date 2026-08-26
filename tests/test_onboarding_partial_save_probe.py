"""Customer Value failing-before: onboarding must not report a durable profile save as wholly failed.

DO NOT MERGE / NOT OWNER REPAIR / NOT CANONICAL.
"""
import api


def test_profile_bootstrap_failure_cannot_masquerade_as_unsaved_profile(monkeypatch, tmp_path):
    """If profile persistence succeeds, later Radar failure must be distinguishable.

    The current route persists the profile before running synchronous Radar
    bootstrap. A bootstrap exception currently becomes a generic 5xx response,
    even though a subsequent GET proves the user's new profile is durable. The
    mobile onboarding surface interprets non-2xx as save failure, so the customer
    cannot know whether retrying means "save again" or "recover Radar".
    """
    monkeypatch.setenv("OBRASIGNAL_DB", str(tmp_path / "partial-onboarding.db"))

    def fail_after_profile_save(_account_id):
        raise RuntimeError("synthetic bootstrap failure after durable profile save")

    monkeypatch.setattr(api, "bootstrap_account", fail_after_profile_save)
    client = api.APP.test_client()
    payload = {
        "name": "Empresa Persistida",
        "activity": "instalações eléctricas",
        "contract_interests": ["instalações eléctricas em escolas"],
        "countries": ["PRT"],
        "min_value": 50000,
        "max_value": 500000,
    }

    response = client.post("/api/v1/profile", json=payload)
    readback = client.get("/api/v1/profile")

    assert readback.status_code == 200
    persisted = readback.get_json()["profile"]
    assert persisted["name"] == "Empresa Persistida"

    # Journey invariant: a generic server failure must never imply that nothing
    # was saved when durable customer state has already changed. A future repair
    # may use explicit partial-success/recovery semantics; this probe deliberately
    # does not prescribe the owner contract.
    assert not (
        response.status_code >= 500 and persisted["name"] == "Empresa Persistida"
    ), "ONBOARDING_PARTIAL_SAVE_AMBIGUITY: profile durable, Radar failed, client sees generic save failure"
