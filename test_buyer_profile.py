from datetime import datetime, timezone
import json
import sqlite3

import pytest

from buyer_profile import build_buyer_profile_snapshot, buyer_identity_from_record
from signal_store import ensure_signal_records, persist_signal_records

NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def _db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_signal_records(conn)
    return conn


def _record(external_id, *, signal_type="TENDER", buyer="Springfield City Council", country="GBR", source="TEST", value=None, currency=None, published_at="2026-08-20T12:00:00+00:00", buyer_identifier=None, **extra):
    record = {
        "source": source,
        "signal_type": signal_type,
        "external_id": external_id,
        "title": f"Record {external_id}",
        "buyer": buyer,
        "country": country,
        "value": value,
        "currency": currency,
        "published_at": published_at,
        "publication_date": published_at[:10] if published_at else None,
        "taxonomy": extra.pop("taxonomy", "CPV"),
        "category_code": extra.pop("category_code", "45200000"),
        "place": extra.pop("place", "Springfield"),
        "source_reference": extra.pop("source_reference", f"ref-{external_id}"),
    }
    if buyer_identifier is not None:
        record["buyer_identifier"] = buyer_identifier
    record.update(extra)
    return record


def _add(conn, *records):
    persist_signal_records(conn, records, observed_at="2026-08-25T00:00:00+00:00")


def _identity(conn, external_id, signal_type="TENDER"):
    row = conn.execute(
        "SELECT * FROM signal_records WHERE external_id=? AND signal_type=?",
        (external_id, signal_type),
    ).fetchone()
    return buyer_identity_from_record(dict(row))


def test_official_identifier_prevents_false_merge_and_allows_name_variant():
    conn = _db()
    _add(
        conn,
        _record("A", buyer_identifier={"scheme": "GB-COH", "id": "123"}),
        _record("B", buyer_identifier={"scheme": "GB-COH", "id": "456"}),
        _record("A2", buyer="Springfield Council", buyer_identifier={"scheme": "GB-COH", "id": "123"}),
    )
    a = _identity(conn, "A")
    b = _identity(conn, "B")
    assert a.buyer_id != b.buyer_id
    snapshot = build_buyer_profile_snapshot(conn, a.buyer_id, "12m", now=NOW)
    assert snapshot.known_opportunity_count == 2
    assert {item["value"] for item in snapshot.identifiers} == {"123"}
    assert snapshot.canonical_name == "Springfield City Council"


def test_same_name_different_jurisdiction_and_department_remain_distinct():
    conn = _db()
    _add(
        conn,
        _record("GB", country="GBR", buyer="Department of Transport"),
        _record("AU", country="AUS", buyer="Department of Transport"),
        _record("WATER", country="GBR", buyer="Department of Transport — Water Department"),
    )
    gb, au, dept = (_identity(conn, key) for key in ("GB", "AU", "WATER"))
    assert len({gb.buyer_id, au.buyer_id, dept.buyer_id}) == 3
    assert build_buyer_profile_snapshot(conn, gb.buyer_id, now=NOW).known_opportunity_count == 1


def test_values_are_type_and_currency_separated_with_procedure_dedup_and_lots():
    conn = _db()
    common = {"buyer_identifier": {"scheme": "TEST-ID", "id": "BUYER-1"}}
    _add(
        conn,
        _record("OP-ORIGINAL", value="1000000", currency="EUR", published_at="2026-04-01T00:00:00Z", ocid="ocds-1", lot_id="lot-1", **common),
        _record("OP-AMEND", value="1200000", currency="EUR", published_at="2026-05-01T00:00:00Z", ocid="ocds-1", lot_id="lot-2", **common),
        _record("OP-GBP", value="500000", currency="GBP", ocid="ocds-2", category_code="45300000", **common),
        _record("AW-1", signal_type="AWARD", value="900000", currency="EUR", ocid="ocds-1", award_id="award-1", **common),
        _record("CT-1", signal_type="CONTRACT", value="875000", currency="EUR", ocid="ocds-1", contract_id="contract-1", **common),
        _record("OLD", value="999", currency="EUR", published_at="2024-01-01T00:00:00Z", ocid="old-1", **common),
    )
    buyer_id = _identity(conn, "OP-ORIGINAL").buyer_id
    snapshot = build_buyer_profile_snapshot(conn, buyer_id, "12m", now=NOW)
    assert snapshot.known_opportunity_count == 2
    assert snapshot.known_award_count == 1
    assert snapshot.known_contract_count == 1
    assert snapshot.observed_lot_count == 2
    assert snapshot.known_published_opportunity_values_by_currency == {"EUR": "1200000", "GBP": "500000"}
    assert snapshot.known_award_values_by_currency == {"EUR": "900000"}
    assert snapshot.known_contract_values_by_currency == {"EUR": "875000"}
    assert {item["code"] for item in snapshot.known_categories} == {"45200000", "45300000"}
    assert any(ref["reference"] == "ref-OP-AMEND" for ref in snapshot.source_refs)
    assert snapshot.known_locations == ({"kind": "source_record_location", "value": "Springfield"},)

    all_observed = build_buyer_profile_snapshot(conn, buyer_id, "all", now=NOW)
    assert all_observed.known_opportunity_count == 3
    assert all_observed.known_published_opportunity_values_by_currency["EUR"] == "1200999"


def test_multiple_awards_and_contracts_for_one_procedure_remain_distinct():
    conn = _db()
    common = {"buyer_identifier": {"scheme": "TEST-ID", "id": "BUYER-MULTI"}, "ocid": "ocds-multi"}
    _add(
        conn,
        _record("OP", **common),
        _record("AW-1-V1", signal_type="AWARD", award_id="award-1", value="100", currency="EUR", published_at="2026-06-01T00:00:00Z", **common),
        _record("AW-1-V2", signal_type="AWARD", award_id="award-1", value="110", currency="EUR", published_at="2026-06-02T00:00:00Z", **common),
        _record("AW-2", signal_type="AWARD", award_id="award-2", value="200", currency="EUR", **common),
        _record("CT-1-V1", signal_type="CONTRACT", contract_id="contract-1", value="90", currency="EUR", published_at="2026-06-01T00:00:00Z", **common),
        _record("CT-1-V2", signal_type="CONTRACT", contract_id="contract-1", value="95", currency="EUR", published_at="2026-06-02T00:00:00Z", **common),
        _record("CT-2", signal_type="CONTRACT", contract_id="contract-2", value="180", currency="EUR", **common),
    )
    buyer_id = _identity(conn, "OP").buyer_id
    snapshot = build_buyer_profile_snapshot(conn, buyer_id, now=NOW)
    assert snapshot.known_opportunity_count == 1
    assert snapshot.known_award_count == 2
    assert snapshot.known_contract_count == 2
    assert snapshot.known_award_values_by_currency == {"EUR": "310"}
    assert snapshot.known_contract_values_by_currency == {"EUR": "275"}


def test_award_and_contract_without_native_ids_fall_back_to_external_identity():
    conn = _db()
    common = {"buyer_identifier": {"scheme": "TEST-ID", "id": "BUYER-FALLBACK"}, "ocid": "same-procedure"}
    _add(
        conn,
        _record("OP", **common),
        _record("AW-A", signal_type="AWARD", value="10", currency="GBP", **common),
        _record("AW-B", signal_type="AWARD", value="20", currency="GBP", **common),
        _record("CT-A", signal_type="CONTRACT", value="30", currency="GBP", **common),
        _record("CT-B", signal_type="CONTRACT", value="40", currency="GBP", **common),
    )
    snapshot = build_buyer_profile_snapshot(conn, _identity(conn, "OP").buyer_id, now=NOW)
    assert snapshot.known_award_count == 2
    assert snapshot.known_contract_count == 2
    assert snapshot.known_award_values_by_currency == {"GBP": "30"}
    assert snapshot.known_contract_values_by_currency == {"GBP": "70"}


def test_noncanonical_amount_strings_are_not_silently_reinterpreted():
    conn = _db()
    common = {"buyer_identifier": {"scheme": "TEST-ID", "id": "BUYER-AMOUNT"}}
    _add(
        conn,
        _record("GOOD", value="1000.50", currency="EUR", **common),
        _record("AMBIGUOUS", value="1,000.50", currency="EUR", **common),
        _record("NEGATIVE", value="-5", currency="EUR", **common),
        _record("HUGE", value="1e999", currency="EUR", **common),
    )
    snapshot = build_buyer_profile_snapshot(conn, _identity(conn, "GOOD").buyer_id, now=NOW)
    assert snapshot.known_opportunity_count == 4
    assert snapshot.known_published_opportunity_values_by_currency == {"EUR": "1000.5"}


def test_zero_known_activity_is_not_claimed_as_real_world_inactivity():
    conn = _db()
    _add(conn, _record("BUYER", signal_type="BUYER_SIGNAL", buyer_identifier={"scheme": "X", "id": "7"}))
    buyer_id = _identity(conn, "BUYER", "BUYER_SIGNAL").buyer_id
    one = build_buyer_profile_snapshot(conn, buyer_id, now=NOW)
    two = build_buyer_profile_snapshot(conn, buyer_id, now=NOW)
    assert one.to_dict() == two.to_dict()
    assert one.known_opportunity_count == one.known_award_count == one.known_contract_count == 0
    joined = " ".join(one.coverage_notes).lower()
    assert "not the buyer's total real-world procurement activity" in joined
    assert "inactive" not in joined


def test_private_tables_are_not_read_and_canonical_signal_rows_are_not_mutated():
    conn = _db()
    _add(conn, _record("PUBLIC", buyer_identifier={"scheme": "X", "id": "8"}))
    buyer_id = _identity(conn, "PUBLIC").buyer_id
    conn.execute("CREATE TABLE private_buyer_notes(account_id TEXT, buyer_id TEXT, note TEXT)")
    conn.execute("INSERT INTO private_buyer_notes VALUES (?,?,?)", ("tenant-a", buyer_id, "SECRET PRIVATE NOTE"))
    conn.commit()
    before = [tuple(row) for row in conn.execute("SELECT * FROM signal_records ORDER BY source, signal_type, external_id")]
    snapshot = build_buyer_profile_snapshot(conn, buyer_id, now=NOW)
    after = [tuple(row) for row in conn.execute("SELECT * FROM signal_records ORDER BY source, signal_type, external_id")]
    assert before == after
    assert "SECRET PRIVATE NOTE" not in json.dumps(snapshot.to_dict())


def test_name_scoped_identity_is_explicit_and_no_fuzzy_merge_occurs():
    conn = _db()
    _add(conn, _record("ONE", buyer="Municipality of X"), _record("TWO", buyer="Municipality of X — Water Department"))
    identity = _identity(conn, "ONE")
    assert identity.identity_strength == "name_scoped"
    snapshot = build_buyer_profile_snapshot(conn, identity.buyer_id, now=NOW)
    assert snapshot.known_opportunity_count == 1
    assert any("no fuzzy merge" in note.lower() for note in snapshot.coverage_notes)


def test_malformed_oversized_and_injection_like_ids_fail_closed():
    conn = _db()
    for invalid in ("not-a-buyer-id", "buyer:v0:name_scoped:' OR 1=1 --", "x" * 1025):
        with pytest.raises(ValueError):
            build_buyer_profile_snapshot(conn, invalid, now=NOW)
