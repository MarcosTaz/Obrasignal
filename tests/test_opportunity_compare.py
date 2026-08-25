import copy
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from opportunity_compare import (
    COMPARISON_DIMENSIONS,
    ComparisonError,
    OpportunityNotFoundError,
    compare_opportunities,
)

NOW = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE tenders (
        id INTEGER PRIMARY KEY, external_id TEXT, source TEXT, title TEXT,
        buyer TEXT, country TEXT, value TEXT, value_numeric REAL, currency TEXT,
        deadline TEXT, place TEXT, procedure_type TEXT, lots TEXT,
        qualification_requirements TEXT, status TEXT, url TEXT, source_reference TEXT
    )""")
    conn.execute("""CREATE TABLE opportunity_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL,
        source TEXT NOT NULL, external_id TEXT NOT NULL, decision TEXT,
        reason TEXT, score INTEGER, confidence INTEGER, features_json TEXT
    )""")
    return conn


def add(conn, id, **kw):
    base = dict(external_id=f"ext-{id}", source="TED", title=f"Opportunity {id}", buyer=None,
                country=None, value=None, value_numeric=None, currency=None, deadline=None,
                place=None, procedure_type=None, lots=None, qualification_requirements=None,
                status=None, url=None, source_reference=None)
    base.update(kw)
    cols = ["id"] + list(base)
    vals = [id] + [base[k] for k in base]
    conn.execute(f"INSERT INTO tenders ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", vals)
    conn.commit()


def decide(conn, account, id, **features):
    conn.execute(
        "INSERT INTO opportunity_decisions(account_id,source,external_id,decision,score,confidence,features_json) VALUES(?,?,?,?,?,?,?)",
        (account, "TED", f"ext-{id}", "REVIEW", 71, 80, json.dumps(features)),
    )
    conn.commit()


def compare(conn, ids, account="acct-a"):
    return compare_opportunities(conn, {"account_id": account}, ids, {"now": NOW})


def test_compare_two_and_preserves_order_and_derived_days():
    conn = db(); add(conn, 2, deadline="2026-08-30T10:00:00Z"); add(conn, 1, deadline="2026-08-27T23:00:00+01:00")
    result = compare(conn, [2, 1])
    assert [x["id"] for x in result["opportunities"]] == [2, 1]
    assert result["values_by_opportunity"]["2"]["days_remaining"]["value"] == 5
    assert result["values_by_opportunity"]["1"]["days_remaining"]["value"] == 2
    assert result["values_by_opportunity"]["1"]["days_remaining"]["origin"] == "DERIVED"


def test_compare_five():
    conn = db()
    for i in range(1, 6): add(conn, i)
    assert len(compare(conn, [1, 2, 3, 4, 5])["opportunities"]) == 5


def test_reject_one_too_many_duplicates_and_malformed_ids():
    conn = db()
    for i in range(1, 7): add(conn, i)
    with pytest.raises(ComparisonError): compare(conn, [1])
    with pytest.raises(ComparisonError): compare(conn, [1, 2, 3, 4, 5, 6])
    with pytest.raises(ComparisonError): compare(conn, [1, 1])
    with pytest.raises(ComparisonError): compare(conn, ["1 OR 1=1", 2])


def test_missing_opportunity():
    conn = db(); add(conn, 1)
    with pytest.raises(OpportunityNotFoundError): compare(conn, [1, 99])


def test_unknown_never_becomes_zero_false_or_poor():
    conn = db(); add(conn, 1); add(conn, 2)
    result = compare(conn, [1, 2])
    cell = result["values_by_opportunity"]["1"]["economic_fit"]
    assert cell == {"status": "UNKNOWN", "value": None, "origin": "DERIVED", "source": "latest account opportunity_decision.features.economic_fit"}
    assert "economic_fit" in result["missing_data"]["1"]


def test_source_availability_is_derived_boolean_and_not_missing():
    conn = db(); add(conn, 1, source="TED"); add(conn, 2, source="")
    result = compare(conn, [1, 2])
    assert result["values_by_opportunity"]["1"]["source_available"] == {"status": "KNOWN", "value": True, "origin": "DERIVED", "source": "presence of canonical source/source_reference/url"}
    assert result["values_by_opportunity"]["2"]["source_available"]["value"] is False


def test_mixed_currencies_are_not_ranked_or_converted():
    conn = db(); add(conn, 1, value="100000", currency="EUR"); add(conn, 2, value="900000", currency="GBP")
    result = compare(conn, [1, 2])
    assert any(w["code"] == "MIXED_CURRENCIES" for w in result["warnings"])
    assert not any(h["key"] == "highest_published_value" for h in result["highlights"])
    assert any(h["key"] == "mixed_currencies" for h in result["highlights"])


def test_same_currency_highlight_is_deterministic():
    conn = db(); add(conn, 1, value_numeric=100, currency="EUR"); add(conn, 2, value_numeric=200, currency="EUR")
    result = compare(conn, [1, 2])
    highlight = next(h for h in result["highlights"] if h["key"] == "highest_published_value")
    assert highlight["opportunity_ids"] == ["2"]


def test_existing_economic_fit_and_capacity_are_reused_per_account():
    conn = db(); add(conn, 1); add(conn, 2)
    decide(conn, "acct-a", 1, economic_fit={"status": "FAVOURABLE", "score": 82}, capability_evidence={"matched": True, "evidence_count": 2})
    decide(conn, "acct-b", 1, economic_fit={"status": "UNFAVOURABLE", "score": 20})
    a = compare(conn, [1, 2], "acct-a")
    b = compare(conn, [1, 2], "acct-b")
    assert a["values_by_opportunity"]["1"]["economic_fit"]["value"]["status"] == "FAVOURABLE"
    assert b["values_by_opportunity"]["1"]["economic_fit"]["value"]["status"] == "UNFAVOURABLE"
    assert a["values_by_opportunity"]["1"]["capacity_fit"]["value"]["evidence_count"] == 2


def test_latest_decision_wins_without_cross_tenant_leakage():
    conn = db(); add(conn, 1); add(conn, 2)
    decide(conn, "acct-a", 1, economic_fit={"status": "REVIEW"})
    decide(conn, "acct-a", 1, economic_fit={"status": "FAVOURABLE"})
    decide(conn, "acct-b", 1, economic_fit={"secret": "other-account"})
    result = compare(conn, [1, 2], "acct-a")
    assert result["values_by_opportunity"]["1"]["economic_fit"]["value"] == {"status": "FAVOURABLE"}
    assert "secret" not in json.dumps(result)


def test_no_mutation_of_source_opportunities_or_decisions():
    conn = db(); add(conn, 1, title="A", value="100", currency="EUR"); add(conn, 2, title="B")
    before_tenders = [dict(r) for r in conn.execute("SELECT * FROM tenders ORDER BY id")]
    before_decisions = [dict(r) for r in conn.execute("SELECT * FROM opportunity_decisions ORDER BY id")]
    compare(conn, [1, 2])
    assert [dict(r) for r in conn.execute("SELECT * FROM tenders ORDER BY id")] == before_tenders
    assert [dict(r) for r in conn.execute("SELECT * FROM opportunity_decisions ORDER BY id")] == before_decisions


def test_output_is_deterministic_with_fixed_clock():
    conn = db(); add(conn, 1, deadline="2026-09-01T00:00:00Z"); add(conn, 2)
    assert compare(conn, [1, 2]) == compare(conn, [1, 2])


def test_all_fields_missing_degrades_gracefully():
    conn = db(); add(conn, 1, source=""); add(conn, 2, source="")
    result = compare(conn, [1, 2])
    assert result["data_completeness"]["1"]["ratio"] < 0.5
    assert result["values_by_opportunity"]["1"]["deadline"]["status"] == "UNKNOWN"


def test_expired_closed_no_deadline_and_null_location_are_factual_or_unknown_only():
    conn = db(); add(conn, 1, deadline="2026-08-20T00:00:00Z", status="CLOSED", place=None); add(conn, 2)
    result = compare(conn, [1, 2])
    assert result["values_by_opportunity"]["1"]["days_remaining"]["value"] == -5
    assert result["values_by_opportunity"]["1"]["opportunity_status"]["value"] == "CLOSED"
    assert result["values_by_opportunity"]["1"]["geography"]["status"] == "UNKNOWN"
    assert result["values_by_opportunity"]["2"]["deadline"]["status"] == "UNKNOWN"


def test_registry_is_central_and_keys_unique():
    keys = [d.key for d in COMPARISON_DIMENSIONS]
    assert len(keys) == len(set(keys))
    assert {"published_value", "deadline", "days_remaining", "economic_fit"}.issubset(keys)


def test_different_countries_large_values_and_identical_rows_except_id():
    conn = db()
    add(conn, 1, country="PRT", value_numeric=10_000_000_000, currency="EUR", buyer="Same")
    add(conn, 2, country="GBR", value_numeric=10_000_000_000, currency="EUR", buyer="Same")
    result = compare(conn, [1, 2])
    assert result["values_by_opportunity"]["1"]["published_value"]["value"]["amount"] == 10_000_000_000
    assert result["values_by_opportunity"]["1"]["geography"]["value"] == "PRT"
    assert result["values_by_opportunity"]["2"]["geography"]["value"] == "GBR"


def test_existing_assessments_are_explicitly_derived_not_facts():
    conn = db(); add(conn, 1); add(conn, 2)
    decide(conn, "acct-a", 1, economic_fit={"status": "FAVOURABLE"}, capability_evidence={"matched": True})
    result = compare(conn, [1, 2])
    assert result["values_by_opportunity"]["1"]["economic_fit"]["origin"] == "DERIVED"
    assert result["values_by_opportunity"]["1"]["capacity_fit"]["origin"] == "DERIVED"
