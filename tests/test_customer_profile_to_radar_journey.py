import sqlite3


def test_profile_mutation_recalculates_before_radar_uses_current_decision(monkeypatch, tmp_path):
    """Synthetic journey proof: saved profile -> recalculation -> current Radar.

    This deliberately uses the real profile normalization, bootstrap and Decision
    Intelligence path. The journey test asserts composition/causality only; it
    does not redefine scoring semantics.
    """
    import api
    import app

    class Identity:
        account_id = "journey-company"
        authenticated = True

    db_path = tmp_path / "profile-to-radar.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setattr(app, "DB", str(db_path))
    monkeypatch.setattr(api, "configured_identity", lambda: Identity())
    app.init_db()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT INTO tenders(
                   source, external_id, title, description, buyer, country, cpv,
                   value, deadline, publication_date, url, score, first_seen,
                   last_seen, market
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "TED",
                "JOURNEY-PAVILION-1",
                "Construção de pavilhão industrial",
                "Construção de pavilhões industriais com estrutura e cobertura",
                "Município Demo",
                "PRT",
                "45213220",
                "250000 EUR",
                "2099-12-31",
                "2099-01-01",
                "https://example.invalid/JOURNEY-PAVILION-1",
                40,
                "2099-01-01T00:00:00+00:00",
                "2099-01-01T00:00:00+00:00",
                "PT",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    client = api.APP.test_client()

    unrelated = client.post(
        "/api/v1/profile",
        json={
            "name": "Software Demo",
            "activity": "desenvolvimento de software",
            "contract_interests": ["software empresarial"],
            "coverage_mode": "portugal",
            "countries": ["PRT"],
            "cpv_prefixes": ["48"],
            "keywords": ["software"],
            "capability_tags": ["software"],
            "min_value": 50000,
            "max_value": 500000,
        },
    )
    assert unrelated.status_code == 200
    assert unrelated.get_json()["radar_recalculated"] == 1

    first_radar = client.get("/api/v1/opportunities?market=PT")
    assert first_radar.status_code == 200
    first_items = first_radar.get_json()["items"]
    assert len(first_items) == 1
    first = first_items[0]
    assert first["external_id"] == "JOURNEY-PAVILION-1"
    assert first["account_score"] is not None
    assert first["account_decision"] is not None
    assert first["decision_reason"]

    matching = client.post(
        "/api/v1/profile",
        json={
            "name": "Pavilhões Demo",
            "activity": "Construção e reabilitação de pavilhões industriais",
            "contract_interests": [
                "Construção de pavilhões industriais",
                "Reabilitação de coberturas",
            ],
            "coverage_mode": "portugal",
            "countries": ["PRT"],
            "cpv_prefixes": ["4521"],
            "keywords": [],
            "capability_tags": ["construção de pavilhões industriais"],
            "min_value": 50000,
            "max_value": 500000,
        },
    )
    assert matching.status_code == 200
    assert matching.get_json()["radar_recalculated"] == 1

    second_radar = client.get("/api/v1/opportunities?market=PT")
    assert second_radar.status_code == 200
    second_items = second_radar.get_json()["items"]
    assert len(second_items) == 1
    second = second_items[0]

    # The immediate Radar read must use the newly recorded account decision,
    # not the previous profile's decision or the global tender fallback score.
    # Decision labels/thresholds remain owned by Decision Intelligence; this
    # composition proof only requires that the profile mutation materially
    # changes the current account-specific decision evidence.
    assert second["external_id"] == first["external_id"]
    assert second["account_score"] > first["account_score"]
    assert second["account_decision"] != first["account_decision"]
    assert second["decision_reason"] != first["decision_reason"]

    detail = client.get(f"/api/v1/opportunities/{second['id']}")
    assert detail.status_code == 200
    current = detail.get_json()
    assert current["account_score"] == second["account_score"]
    assert current["account_decision"] == second["account_decision"]
    assert current["decision_reason"] == second["decision_reason"]

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """SELECT id, score FROM opportunity_decisions
               WHERE account_id=? AND source=? AND external_id=?
               ORDER BY id""",
            ("journey-company", "TED", "JOURNEY-PAVILION-1"),
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 2
    assert rows[-1][1] == second["account_score"]
    assert rows[-1][1] > rows[0][1]
