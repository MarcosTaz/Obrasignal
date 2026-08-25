from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

import app
import api
import cors_app
from opportunity_lifecycle import persist_lifecycle_observations


ROOT = Path(__file__).resolve().parents[1]
PERSONAS = ROOT / "acceptance" / "personas.json"
GOLDEN_PATHS = ROOT / "acceptance" / "golden_paths.json"


REQUIRED_PERSONA_FIELDS = {
    "tenant_account",
    "home_base",
    "work_radius_km",
    "crew_count",
    "crew_skills",
    "crew_available_from",
    "target_contract_value",
    "equipment_available",
    "vehicle_assumptions",
    "financial_constraints",
    "certifications_known",
    "certifications_unknown",
    "geographic_restrictions",
    "work_type_interests",
    "unknown_company_facts",
}

REQUIRED_SCENARIO_FIELDS = {
    "scenario_id",
    "persona",
    "required_capabilities",
    "optional_capabilities",
    "preconditions",
    "steps",
    "expected_truths",
    "forbidden_claims",
    "tenant_scope",
    "external_dependencies",
    "acceptance_level",
    "execution_status",
}

EXECUTION_STATUSES = {
    "CURRENTLY_EXECUTABLE",
    "PARTIALLY_EXECUTABLE",
    "BRANCH-CANDIDATE",
    "BLOCKED_BY_INTEGRATION",
    "BLOCKED_BY_EXTERNAL_CONDITION",
    "FUTURE_CAPABILITY",
}


@pytest.fixture
def golden_db(monkeypatch, tmp_path):
    db_path = tmp_path / "golden-acceptance.db"
    monkeypatch.setenv("OBRASIGNAL_DB", str(db_path))
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "acceptance-tenant-small-trade")
    monkeypatch.setattr(app, "DB", str(db_path))
    app.init_db()
    conn = app.db()
    conn.execute(
        """INSERT INTO tenders(source, external_id, title, description, buyer, country,
           cpv, value, deadline, publication_date, url, score, first_seen, last_seen, market)
           VALUES ('TED','GOLD-OPEN-1','Reabilitação de escola','Pintura e acabamentos',
           'Município Alpha','PRT','45442100','240000 EUR','2099-10-01','2026-08-20',
           'https://example.test/gold-open',88,'2026-08-20','2026-08-20','PT')"""
    )
    conn.execute(
        """INSERT INTO tenders(source, external_id, title, description, buyer, country,
           cpv, value, deadline, publication_date, url, score, first_seen, last_seen, market)
           VALUES ('BASE','GOLD-CLOSED-1','Reabilitação de arquivo','Pintura interior',
           'Município Beta','PRT','45442100','90000 EUR','2020-01-01','2020-01-01',
           'https://example.test/gold-closed',70,'2020-01-01','2020-01-01','PT')"""
    )
    conn.execute(
        """INSERT INTO tenders(source, external_id, title, description, buyer, country,
           cpv, value, deadline, publication_date, url, score, first_seen, last_seen, market)
           VALUES ('TED','GOLD-UNKNOWN-1','Obra com dados incompletos','Informação parcial',
           'Município Gamma','PRT',NULL,NULL,NULL,'2026-08-20',
           'https://example.test/gold-unknown',75,'2026-08-20','2026-08-20','PT')"""
    )
    conn.commit()
    ids = {
        row[1]: row[0]
        for row in conn.execute(
            "SELECT id, external_id FROM tenders WHERE external_id LIKE 'GOLD-%'"
        ).fetchall()
    }
    conn.close()
    return ids


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _items(client, query=""):
    response = client.get(f"/api/v1/opportunities{query}")
    assert response.status_code == 200
    return response.get_json()["items"]


def _insert_deadline_fixture(external_id, deadline):
    conn = app.db()
    try:
        cur = conn.execute(
            """INSERT INTO tenders(source, external_id, title, description, buyer, country,
               cpv, value, deadline, publication_date, url, score, first_seen, last_seen, market)
               VALUES ('TED',?,?,?,?, 'PRT','45442100','100000 EUR',?,'2026-08-25',?,80,
               '2026-08-25','2026-08-25','PT')""",
            (
                external_id,
                f"Fixture {external_id}",
                "Golden temporal precision fixture",
                "Município Delta",
                deadline,
                f"https://example.test/{external_id.lower()}",
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def test_persona_contract_keeps_required_facts_and_unknowns_explicit():
    data = _load(PERSONAS)
    personas = data["personas"]
    assert {p["type"] for p in personas} == {
        "SMALL_TRADE_CONTRACTOR",
        "SPECIALIST_CONTRACTOR",
        "GENERAL_CONTRACTOR",
        "MOBILE_CREW_CONTRACTOR",
        "CAPITAL_CONSTRAINED_CONTRACTOR",
    }
    for persona in personas:
        assert REQUIRED_PERSONA_FIELDS <= persona.keys()
        assert persona["tenant_account"]
        assert persona["crew_count"] > 0
        assert persona["unknown_company_facts"], persona["id"]
        assert persona["certifications_unknown"], persona["id"]


def test_golden_contract_is_machine_readable_and_never_infers_pass():
    data = _load(GOLDEN_PATHS)
    persona_ids = {p["id"] for p in _load(PERSONAS)["personas"]}
    assert data["fixture_clock"] == "2026-08-25T12:00:00Z"
    assert data["truth_policy"]["unknown_is_not_zero"] is True
    assert data["truth_policy"]["no_false_success"] is True
    for scenario in data["scenarios"]:
        assert REQUIRED_SCENARIO_FIELDS <= scenario.keys()
        assert scenario["persona"] in persona_ids
        assert scenario["execution_status"] in EXECUTION_STATUSES
        assert scenario["expected_truths"]
        assert scenario["forbidden_claims"]
        assert not any(str(value).upper() == "PASS" for value in scenario.values())


def test_discover_detail_preserves_source_and_unknown_semantics(golden_db):
    client = api.APP.test_client()

    open_items = _items(client, "?open=1")
    assert [item["external_id"] for item in open_items] == ["GOLD-OPEN-1"]

    open_detail = client.get(
        f"/api/v1/opportunities/{golden_db['GOLD-OPEN-1']}"
    )
    assert open_detail.status_code == 200
    open_body = open_detail.get_json()
    assert open_body["source"] == "TED"
    assert open_body["url"] == "https://example.test/gold-open"
    assert open_body["is_open"] is True
    assert open_body["deadline_status"]["state"] == "open"

    unknown_detail = client.get(
        f"/api/v1/opportunities/{golden_db['GOLD-UNKNOWN-1']}"
    )
    assert unknown_detail.status_code == 200
    unknown_body = unknown_detail.get_json()
    assert unknown_body["value"] is None
    assert unknown_body["deadline"] is None
    assert unknown_body["deadline_status"]["state"] == "unknown"
    assert unknown_body["is_open"] is False
    assert unknown_body["url"] == "https://example.test/gold-unknown"


def test_closed_opportunity_is_never_open(golden_db):
    client = api.APP.test_client()
    closed = client.get(
        f"/api/v1/opportunities/{golden_db['GOLD-CLOSED-1']}"
    ).get_json()
    assert closed["deadline_status"]["state"] == "closed"
    assert closed["is_open"] is False
    assert all(item["external_id"] != "GOLD-CLOSED-1" for item in _items(client, "?open=1"))


def test_expired_opportunity_is_not_actionable_without_stronger_current_evidence(golden_db):
    client = api.APP.test_client()
    closed = client.get(
        f"/api/v1/opportunities/{golden_db['GOLD-CLOSED-1']}"
    ).get_json()
    assert closed["deadline_status"]["state"] == "closed"
    assert closed["is_actionable"] is False
    assert closed["is_open"] is False
    assert all(
        item["external_id"] != "GOLD-CLOSED-1"
        for item in _items(client)
    )


def test_explicit_source_lifecycle_open_closed_precedence(golden_db):
    conn = app.db()
    try:
        persist_lifecycle_observations(
            conn,
            [
                {
                    "source": "BASE",
                    "external_id": "GOLD-CLOSED-1",
                    "is_actionable": True,
                    "lifecycle_status": "open",
                    "lifecycle_reason": "publisher explicitly reopened",
                },
                {
                    "source": "TED",
                    "external_id": "GOLD-OPEN-1",
                    "is_actionable": False,
                    "lifecycle_status": "cancelled",
                    "lifecycle_reason": "publisher explicitly cancelled",
                },
            ],
        )
    finally:
        conn.close()

    client = api.APP.test_client()
    reopened = client.get(
        f"/api/v1/opportunities/{golden_db['GOLD-CLOSED-1']}"
    ).get_json()
    cancelled = client.get(
        f"/api/v1/opportunities/{golden_db['GOLD-OPEN-1']}"
    ).get_json()

    assert reopened["deadline_status"]["state"] == "closed"
    assert reopened["is_actionable"] is True
    assert reopened["lifecycle_status"] == "open"
    assert cancelled["deadline_status"]["state"] == "open"
    assert cancelled["is_actionable"] is False
    assert cancelled["lifecycle_status"] == "cancelled"


def test_missing_and_unparseable_deadlines_remain_unknown_compatible(golden_db):
    client = api.APP.test_client()
    missing = client.get(
        f"/api/v1/opportunities/{golden_db['GOLD-UNKNOWN-1']}"
    ).get_json()
    assert missing["deadline_status"]["state"] == "unknown"
    assert missing["is_actionable"] is True
    assert missing["is_open"] is False

    invalid_id = _insert_deadline_fixture("GOLD-INVALID-DEADLINE", "not-a-date")
    invalid = client.get(f"/api/v1/opportunities/{invalid_id}").get_json()
    assert invalid["deadline_status"]["state"] == "unknown"
    assert invalid["is_actionable"] is True
    assert invalid["is_open"] is False


def test_date_only_current_day_does_not_fabricate_exact_closing_time(golden_db):
    today = datetime.now(timezone.utc).date().isoformat()
    opportunity_id = _insert_deadline_fixture("GOLD-DATE-ONLY-TODAY", today)
    client = api.APP.test_client()
    detail = client.get(f"/api/v1/opportunities/{opportunity_id}").get_json()

    assert detail["deadline"] == today
    assert detail["deadline_status"]["state"] == "unknown"
    assert detail["is_actionable"] is True
    assert detail["is_open"] is False


def test_production_composition_has_exactly_one_api_owned_opportunity_detail_route():
    rules = [
        rule
        for rule in cors_app.APP.url_map.iter_rules()
        if rule.rule == "/api/v1/opportunities/<int:opportunity_id>"
    ]
    assert len(rules) == 1
    assert rules[0].endpoint == "mobile_api.opportunity_detail"
    assert cors_app.APP.view_functions[rules[0].endpoint] is api.opportunity_detail
    assert not hasattr(cors_app, "_opportunity_detail")


def test_private_workflow_state_is_tenant_isolated_but_is_not_called_watchlist(golden_db, monkeypatch):
    client = api.APP.test_client()
    opportunity_id = golden_db["GOLD-OPEN-1"]

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "acceptance-account-a")
    saved = client.post(
        f"/api/v1/opportunities/{opportunity_id}/workflow",
        json={"status": "PREPARING", "note": "Acceptance tenant A only", "account_id": "acceptance-account-b"},
    )
    assert saved.status_code == 200
    assert saved.get_json()["account_id"] == "acceptance-account-a"

    own = client.get(f"/api/v1/opportunities/{opportunity_id}").get_json()["workflow"]
    assert own["status"] == "PREPARING"
    assert own["note"] == "Acceptance tenant A only"

    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "acceptance-account-b")
    other = client.get(f"/api/v1/opportunities/{opportunity_id}").get_json()["workflow"]
    assert other["status"] == "NEW"
    assert other["note"] is None


def test_provider_mode_requires_authentication_for_golden_opportunity_read(monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "provider")
    monkeypatch.setenv("OBRASIGNAL_JWT_ISSUER", "https://acceptance.example/auth/v1")

    response = api.APP.test_client().get("/api/v1/opportunities")

    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication_required"
