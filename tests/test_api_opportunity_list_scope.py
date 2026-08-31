from pathlib import Path


def test_default_opportunity_list_is_account_scoped_across_markets():
    source = Path("api.py").read_text(encoding="utf-8")

    assert 'market = (request.args.get("market") or "").upper().strip()' in source
    assert 'where = [actionable_predicate("lc", "t"), "d.id IS NOT NULL"]' in source
    assert 'WHERE account_id=? GROUP BY source, external_id' in source


def test_legacy_implicit_portugal_default_is_not_reintroduced():
    source = Path("api.py").read_text(encoding="utf-8")

    assert 'request.args.get("market") or "PT"' not in source
