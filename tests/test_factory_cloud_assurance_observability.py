from datetime import date

from factory_cloud.assurance_observability import assurance_health
from vertical_apps.aviation_recovery.web import create_app as create_aviation_app
from vertical_apps.contractcredit import ContractCreditService
from vertical_apps.contractcredit.web import create_app as create_contractcredit_app


def test_missing_database_is_fail_closed_without_activity_counts(tmp_path):
    health = assurance_health(tmp_path / "missing.sqlite3")
    assert health.status == "unavailable"
    assert health.integrity == "missing"
    assert health.schema_version is None
    assert health.public_dict() == {
        "status": "unavailable",
        "integrity": "missing",
        "schema_version": None,
    }


def test_operational_metrics_are_separate_from_public_readiness(tmp_path):
    path = tmp_path / "contractcredit.sqlite3"
    service = ContractCreditService(path)
    service.analyze(
        tenant_id="sensitive-tenant-name",
        actor_id="sensitive-actor",
        contract_ref="sensitive-contract-ref",
        incident_ref="sensitive-incident-ref",
        monthly_fee="50000",
        credit_rate="0.10",
        notice_due=date(2026, 9, 15),
    )
    health = assurance_health(path)
    public = health.public_dict()
    assert public == {"status": "ready", "integrity": "ok", "schema_version": 1}
    assert "open_findings" not in public
    assert "pending_notifications" not in public
    assert "audit_events" not in public

    operational = health.operational_dict()
    assert operational["open_findings"] == 1
    assert operational["pending_notifications"] == 1
    assert operational["audit_events"] == 1
    rendered = str(operational)
    assert "sensitive-tenant-name" not in rendered
    assert "sensitive-contract-ref" not in rendered


def test_vertical_readiness_endpoints_expose_no_activity_counts(tmp_path):
    for create_app, filename, vertical in (
        (create_aviation_app, "aviation.sqlite3", "aviation-lease-entitlement-recovery"),
        (create_contractcredit_app, "credit.sqlite3", "contractcredit"),
    ):
        client = create_app(tmp_path / filename).test_client()
        response = client.get("/ready")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["status"] == "ready"
        assert payload["integrity"] == "ok"
        assert payload["vertical"] == vertical
        assert payload["mode"] == "assisted"
        for forbidden in ("tenant_id", "actor_id", "open_findings", "pending_notifications", "audit_events"):
            assert forbidden not in payload
