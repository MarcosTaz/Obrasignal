from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "factories" / "industrial-claims"
LEDGER = BASE / "OUTBOUND_LEDGER.json"
PACK = BASE / "OUTBOUND_MESSAGE_PACK.md"
ROUTES = BASE / "CONTACT_ROUTE_MATRIX.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_outbound_ledger_has_exactly_ten_unique_prepared_records():
    data = _json(LEDGER)
    records = data["records"]
    assert len(records) == 10
    ids = [record["account_id"] for record in records]
    assert len(ids) == len(set(ids)) == 10
    assert all(record["status"] == "PREPARED_NOT_SENDABLE" for record in records)
    assert all(record["founder_send_authorization_required"] is True for record in records)


def test_outbound_records_all_bind_to_known_contact_routes():
    routes = _json(ROUTES)["routes"]
    route_ids = {route["account_id"] for route in routes}
    for record in _json(LEDGER)["records"]:
        assert record["route_account_id"] in route_ids


def test_truth_state_machine_cannot_promote_delivery_reply_or_meeting():
    truth = _json(LEDGER)["truth_rules"]
    assert truth["delivery_is_interest"] is False
    assert truth["reply_is_qualification"] is False
    assert truth["meeting_is_paid_customer"] is False
    assert truth["metadata_is_leakage_proof"] is False
    assert truth["outbound_authorized"] is False
    assert truth["confidential_document_request_allowed"] is False


def test_role_and_route_rechecks_are_preserved():
    records = {r["account_id"]: r for r in _json(LEDGER)["records"]}
    assert records["mold-tech-portugal-pt"]["role_recheck_required"] is True
    for account in ("tmg-automotive-pt", "plastifa-pt", "transformade-pt", "epalfer-pt"):
        assert records[account]["route_recheck_required"] is True


def test_message_pack_stays_metadata_only_and_document_free():
    text = PACK.read_text(encoding="utf-8")
    lower = text.lower()
    assert "prepared_not_sendable" in lower
    assert "não pedimos documentos" in lower or "no documents are requested" in lower
    assert "no attachments" in lower
    assert "no quantified recovery claim" in lower
    assert "a delivery receipt is not buyer interest" in lower
    assert "a reply is not qualification" in lower
    assert "a meeting is not a paid customer" in lower


def test_message_pack_has_no_cross_project_sender_identity():
    lower = PACK.read_text(encoding="utf-8").lower()
    for forbidden in ("certactum.com", "varactum", "obrasignal.com", "contractcredit"):
        assert forbidden not in lower
