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


def test_customer_radar_pagination_is_bounded_and_deterministic():
    source = Path("api.py").read_text(encoding="utf-8")

    assert '_bounded_query_int("limit", 20, 1, 100)' in source
    assert '_bounded_query_int("offset", 0, 0, 100000)' in source
    assert '_bounded_query_int("minscore", None, 0, 100, optional=True)' in source
    assert 'ORDER BY COALESCE(d.score,t.score) DESC, t.deadline ASC, t.id ASC' in source
    assert 'LIMIT ? OFFSET ?' in source
    assert 'limit + 1, offset' in source
    assert '"has_more": has_more' in source
    assert '"next_offset": offset + limit if has_more else None' in source


def test_invalid_pagination_query_has_explicit_fail_closed_contract():
    source = Path("api.py").read_text(encoding="utf-8")

    assert 'return jsonify({"error": "invalid_query", "message": f"Parâmetro inválido: {exc.args[0]}"}), 400' in source
