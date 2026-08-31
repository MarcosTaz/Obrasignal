from pathlib import Path


def test_default_opportunity_list_is_account_scoped_across_markets():
    source = Path("api.py").read_text(encoding="utf-8")

    assert 'market = (request.args.get("market") or "").upper().strip()' in source
    assert 'where = [actionable_predicate("lc", "t")]' in source
    assert 'FROM opportunity_decisions d' in source
    assert 'FROM opportunity_decisions WHERE account_id=? GROUP BY source, external_id' in source
    assert 'JOIN tenders t ON t.source=d.source AND t.external_id=d.external_id' in source
    assert 'WHERE d.account_id=?' in source


def test_legacy_implicit_portugal_default_is_not_reintroduced():
    source = Path("api.py").read_text(encoding="utf-8")

    assert 'request.args.get("market") or "PT"' not in source
