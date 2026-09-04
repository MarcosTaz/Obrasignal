from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "factories" / "industrial-claims" / "CONTACT_ROUTE_MATRIX.json"
SENDER_RULES = ROOT / "factories" / "industrial-claims" / "SENDER_IDENTITY_REQUIREMENTS.md"


def _matrix() -> dict:
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def test_contact_route_matrix_contains_exactly_ten_unique_accounts():
    data = _matrix()
    routes = data["routes"]
    assert len(routes) == 10
    account_ids = [route["account_id"] for route in routes]
    assert len(account_ids) == len(set(account_ids)) == 10


def test_contact_routes_remain_corporate_and_not_authorized_for_outbound():
    data = _matrix()
    assert data["global_truth"]["outbound_authorized"] is False
    assert data["global_truth"]["sender_identity_ready"] is False
    assert data["global_truth"]["personal_emails_inferred"] is False
    assert data["global_truth"]["personal_phones_inferred"] is False

    for route in data["routes"]:
        assert route["channel_scope"].startswith("CORPORATE_")
        assert route["outbound_authorized"] is False
        assert route["source_url"].startswith("https://")
        assert route["route_confidence"] in {"HIGH_OFFICIAL", "MEDIUM_CORROBORATED"}
        if route["route_confidence"] == "MEDIUM_CORROBORATED":
            assert route["requires_recheck_before_send"] is True


def test_no_cross_project_sender_or_recipient_identity_is_smuggled_into_matrix():
    raw = MATRIX.read_text(encoding="utf-8").lower()
    forbidden = (
        "certactum.com",
        "varactum",
        "obrasignal.com",
        "contractcredit",
        "marcos@certactum.com",
    )
    for value in forbidden:
        assert value not in raw


def test_matrix_cannot_claim_market_or_recovery_truth():
    truth = _matrix()["global_truth"]
    assert truth["buyer_interest_proven"] is False
    assert truth["leakage_proven"] is False
    assert truth["recoverable_value_proven"] is False
    assert truth["confidential_documents_requested"] is False


def test_sender_identity_rules_keep_real_send_as_explicit_boundary():
    text = SENDER_RULES.read_text(encoding="utf-8")
    assert "OUTBOUND_STATE = PREPARED_NOT_SENDABLE" in text
    assert "No domain is selected or purchased" in text
    assert "user has authorized the real external send step" in text
    assert "Do not infer, scrape or synthesize personal recipient email addresses" in text
