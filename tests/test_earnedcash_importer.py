from earnedcash.importer import parse_ledger_csv
from earnedcash.ledger import LedgerKind


HEADER = "record_id,tenant_id,customer_id,project_id,currency,kind,amount,relates_to,verified,due\n"


def test_csv_import_preserves_lineage_and_types():
    text = HEADER + (
        "a1,t1,c1,p1,gbp,application,100,,true,\n"
        "c1,t1,c1,p1,GBP,certificate,100,a1,true,\n"
        "i1,t1,c1,p1,GBP,invoice,100,c1,true,true\n"
    )
    result = parse_ledger_csv(text, expected_tenant_id="t1")
    assert result.rejected is False
    assert result.issues == ()
    assert result.records[2].kind == LedgerKind.INVOICE
    assert result.records[2].due is True
    assert result.records[2].currency == "GBP"


def test_cross_tenant_csv_rejects_entire_import():
    text = HEADER + (
        "a1,t1,c1,p1,GBP,application,100,,true,\n"
        "i1,t2,c1,p1,GBP,invoice,100,a1,true,true\n"
    )
    result = parse_ledger_csv(text, expected_tenant_id="t1")
    assert result.rejected is True
    assert result.records == ()
    assert any(issue.code == "TENANT_MISMATCH" for issue in result.issues)


def test_missing_columns_rejects_import():
    result = parse_ledger_csv("record_id,amount\nx,10\n", expected_tenant_id="t1")
    assert result.rejected is True
    assert result.records == ()
    assert result.issues[0].code == "MISSING_COLUMNS"


def test_invalid_amount_is_not_silently_coerced():
    text = HEADER + "a1,t1,c1,p1,GBP,application,not-money,,true,\n"
    result = parse_ledger_csv(text, expected_tenant_id="t1")
    assert len(result.records) == 0
    assert result.issues[0].code == "INVALID_ROW"


def test_non_finite_amount_is_rejected_row():
    text = HEADER + "a1,t1,c1,p1,GBP,application,NaN,,true,\n"
    result = parse_ledger_csv(text, expected_tenant_id="t1")
    assert len(result.records) == 0
    assert result.issues[0].code == "INVALID_ROW"
