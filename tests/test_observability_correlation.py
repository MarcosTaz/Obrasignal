from pathlib import Path

from observability_correlation import (
    assess_correlation_candidate,
    current_repository_correlation_report,
    scan_notification_event_key,
    scan_request_correlation,
)


ROOT = Path(__file__).resolve().parents[1]


def test_safe_operational_correlation_must_be_opaque_and_operation_scoped():
    result = assess_correlation_candidate(
        "correlation_id",
        opaque=True,
        stable_one_operation=True,
    )

    assert result.classification == "SAFE_CORRELATION"
    assert result.reusable_as_operational_correlation is True
    assert result.reasons == ()


def test_tenant_identity_must_not_be_reused_as_correlation():
    result = assess_correlation_candidate(
        "account_key",
        opaque=False,
        embeds_tenant_identity=True,
        stable_one_operation=True,
    )

    assert result.classification == "UNSAFE_AS_CORRELATION"
    assert result.reusable_as_operational_correlation is False
    assert "TENANT_IDENTITY_EMBEDDED" in result.reasons


def test_domain_idempotency_key_is_not_operational_correlation():
    result = assess_correlation_candidate(
        "event_key",
        opaque=False,
        embeds_domain_identity=True,
        stable_one_operation=False,
    )

    assert result.classification == "DOMAIN_ID_NOT_CORRELATION"
    assert result.reusable_as_operational_correlation is False


def test_customer_content_is_never_safe_correlation():
    result = assess_correlation_candidate(
        "email",
        opaque=False,
        customer_content=True,
        stable_one_operation=True,
    )

    assert result.classification == "UNSAFE_AS_CORRELATION"
    assert "CUSTOMER_CONTENT" in result.reasons


def test_current_notification_event_key_embeds_tenant_and_domain_identity():
    source = (ROOT / "notification_events.py").read_text(encoding="utf-8")
    result = scan_notification_event_key(source)

    assert result.classification == "UNSAFE_AS_CORRELATION"
    assert result.embeds_tenant_identity is True
    assert result.embeds_domain_identity is True
    assert result.reusable_as_operational_correlation is False


def test_request_correlation_missing_stays_unknown():
    result = scan_request_correlation(
        {
            "api.py": "def endpoint():\n    return {'ok': True}\n",
            "worker.py": "def worker():\n    return None\n",
        }
    )

    assert result == {
        "state": "UNKNOWN",
        "identifiers": {},
        "finding": "NO_EXPLICIT_REQUEST_CORRELATION",
    }


def test_explicit_request_correlation_is_inventory_only_not_semantic_approval():
    result = scan_request_correlation(
        {"api.py": "def endpoint(request_id):\n    return request_id\n"}
    )

    assert result["state"] == "PROVEN"
    assert result["identifiers"] == {"api.py": ["request_id"]}
    assert result["finding"] is None


def test_current_repository_has_no_explicit_request_correlation_contract():
    report = current_repository_correlation_report(ROOT)

    assert report["request"]["state"] == "UNKNOWN"
    assert report["request"]["identifiers"] == {}
    assert report["request"]["finding"] == "NO_EXPLICIT_REQUEST_CORRELATION"
    event_key = report["notification_event_key"]
    assert event_key["classification"] == "UNSAFE_AS_CORRELATION"
    assert event_key["reusable_as_operational_correlation"] is False
