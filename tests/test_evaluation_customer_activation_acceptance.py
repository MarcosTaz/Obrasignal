import api


def test_completed_profile_records_profile_ready_without_starting_evaluation_clock(monkeypatch, tmp_path):
    monkeypatch.setenv("OBRASIGNAL_DB", str(tmp_path / "golden-evaluation.db"))
    # Profile readiness is a customer event in its own right. A missing shortlist
    # must not be needed merely to prove the completed-profile requirement.
    monkeypatch.setattr(api, "bootstrap_account", lambda _account_id: 0)

    client = api.APP.test_client()
    response = client.post("/api/v1/profile", json={
        "name": "Golden Contractor",
        "activity": "instalacoes eletricas",
        "contract_interests": ["instalacoes eletricas em edificios publicos"],
        "coverage_mode": "portugal",
        "countries": ["PRT"],
    })
    assert response.status_code == 200

    billing = client.get("/api/v1/billing/status")
    assert billing.status_code == 200
    evaluation = billing.get_json()["evaluation"]

    assert evaluation is not None
    assert evaluation["activation_requirements"]["profile_ready"] is True, (
        "GAP-GP-013: a customer can persist a complete profile but the Evaluation "
        "lifecycle does not observe profile_ready. Policy-level manual event tests "
        "do not prove the real customer journey."
    )
    assert evaluation["activation_requirements"]["market_data_available"] is False
    assert evaluation["activation_requirements"]["first_relevant_shortlist_generated"] is False
    assert evaluation["activated_at"] is None
    assert evaluation["ends_at"] is None
