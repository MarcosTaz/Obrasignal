import json
import sqlite3
from datetime import date

from contract_expiry import evaluate_contract_expiry
from signal_store import get_signal_record, persist_signal_records


def test_expiry_read_model_persists_as_non_tender_signal_with_provenance():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    assessment = evaluate_contract_expiry({
        "signal_type": "CONTRACT",
        "contract_id": "contract-42",
        "contract_status": "ACTIVE",
        "contract_end_date": "2027-02-01",
        "source_reference": "register:42",
        "contract_value": "2800000",
        "currency": "EUR",
    }, date(2026, 8, 25))
    row = assessment.as_signal_record()
    assert persist_signal_records(conn, [row], observed_at="2026-08-25T01:00:00Z") == 1
    stored = get_signal_record(conn, "CONTRACT_EXPIRY_ENGINE", assessment.signal_id, "CONTRACT_EXPIRY")
    assert stored["signal_type"] == "CONTRACT_EXPIRY"
    assert stored["target_date"] == "2027-02-01"
    snapshot = json.loads(stored["normalized_json"])
    assert snapshot["contract_id"] == "contract-42"
    assert snapshot["end_date_basis"] == "OFFICIAL"
    assert snapshot["prior_known_contract_value"] == "2800000"
    assert snapshot["replacement_procurement_confirmed"] is False
    assert snapshot["is_open_tender"] is False


def test_repeated_persistence_same_state_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    contract = {"signal_type":"CONTRACT", "contract_id":"C", "contract_status":"ACTIVE", "contract_end_date":"2027-01-01"}
    row = evaluate_contract_expiry(contract, date(2026, 8, 25)).as_signal_record()
    persist_signal_records(conn, [row], observed_at="2026-08-25T01:00:00Z")
    persist_signal_records(conn, [row], observed_at="2026-08-25T02:00:00Z")
    assert conn.execute("SELECT COUNT(*) FROM signal_records WHERE signal_type='CONTRACT_EXPIRY'").fetchone()[0] == 1
