from earnedcash.importer import (
    parse_ledger_csv,
    parse_operator_verified_ledger_csv,
)
from earnedcash.ledger import LedgerKind


CLIENT_HEADER = "record_id,tenant_id,customer_id,project_id,currency,kind,amount,relates_to\n"
OPERATOR_HEADER = CLIENT_HEADER.rstrip("\n") + ",verified,due\n"


def test_client_csv_import_preserves_lineage_but_not_truth_state():
    text = CLIENT_HEADER + (
        "a1,t1,c1,p1,gbp,application,100,\n"
        "c1,t1,c1,p1,GBP,certificate,100,a1\n"
        "i1,t1,c1,p1,GBP,invoice,100,c1\n"
    )
    result = parse_ledger_csv(text, expected_tenant_id="t1")
    assert result.rejected is False
    assert result.issues == ()
    assert result.records[2].kind == LedgerKind.INVOICE
    assert result.records[2].due is None
    assert result.records[2].verified is False
    assert result.records[2].currency == "GBP"


def test_client_csv_cannot_supply_server_controlled_truth_columns():
    text = OPERATOR_HEADER + (
        "a1,t1,c1,p1,GBP,application,100,,true,\n"
    )
    result = parse_ledger_csv(text, expected_tenant_id="t1")
    assert result.rejected is True
    assert result.records == ()
    assert result.issues[0].code == "SERVER_CONTROLLED_COLUMNS"
    assert "verified" in result.issues[0].detail


def test_operator_verified_csv_can_preserve_reviewed_truth_state():
    text = OPERATOR_HEADER + (
        "a1,t1,c1,p1,gbp,application,100,,true,\n"
        "c1,t1,c1,p1,GBP,certificate,100,a1,true,\n"
        "i1,t1,c1,p1,GBP,invoice,100,c1,true,true\n"
    )
    result = parse_operator_verified_ledger_csv(text, expected_tenant_id="t1")
    assert result.rejected is False
    assert result.issues == ()
    assert result.records[2].kind == LedgerKind.INVOICE
    assert result.records[2].due is True
    assert result.records[2].verified is True
    assert result.records[2].currency == "GBP"


def test_cross_tenant_csv_rejects_entire_import():
    text = CLIENT_HEADER + (
        "a1,t1,c1,p1,GBP,application,100,\n"
        "i1,t2,c1,p1,GBP,invoice,100,a1\n"
    )
    result = parse_ledger_csv(text, expected_tenant_id="t1")
    assert result.rejected is True
    assert result.records == ()
    assert any(issue.code == "TENANT_MISMATCH" for issue in result.issues)


def test_operator_cross_tenant_csv_rejects_entire_import():
    text = OPERATOR_HEADER + (
        "a1,t1,c1,p1,GBP,application,100,,true,\n"
        "i1,t2,c1,p1,GBP,invoice,100,a1,true,true\n"
    )
    result = parse_operator_verified_ledger_csv(text, expected_tenant_id="t1")
    assert result.rejected is True
    assert result.records == ()
    assert any(issue.code == "TENANT_MISMATCH" for issue in result.issues)


def test_missing_columns_rejects_import():
    result = parse_ledger_csv("record_id,amount\nx,10\n", expected_tenant_id="t1")
    assert result.rejected is True
    assert result.records == ()
    assert result.issues[0].code == "MISSING_COLUMNS"


def test_invalid_amount_is_not_silently_coerced():
    text = CLIENT_HEADER + "a1,t1,c1,p1,GBP,application,not-money,\n"
    result = parse_ledger_csv(text, expected_tenant_id="t1")
    assert len(result.records) == 0
    assert result.issues[0].code == "INVALID_ROW"


def test_non_finite_amount_is_rejected_row():
    text = CLIENT_HEADER + "a1,t1,c1,p1,GBP,application,NaN,\n"
    result = parse_ledger_csv(text, expected_tenant_id="t1")
    assert len(result.records) == 0
    assert result.issues[0].code == "INVALID_ROW"
