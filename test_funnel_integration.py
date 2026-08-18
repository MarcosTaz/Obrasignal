import sqlite3

from decision_log import ensure_decision_table, latest_decision
from funnel_integration import persist_and_classify


def test_persist_and_classify_records_auditable_decision():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    item = {
        'source': 'TED',
        'external_id': '2026-S-999',
        'score': 81,
        'deadline': '2026-08-30',
        'market': 'EU',
    }
    decision, reason = persist_and_classify(conn, item, True)

    assert decision == 'RELEVANT'
    assert reason == 'HIGH_COMMERCIAL_SCORE'
    row = latest_decision(conn, 'TED', '2026-S-999')
    assert row['decision'] == 'RELEVANT'
    assert row['features']['is_new'] is True
    assert row['features']['market'] == 'EU'


def test_persist_and_classify_preserves_full_pipeline_evidence():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    item = {
        'source': 'TED',
        'external_id': '2026-S-1000',
        'score': 90,
        'deadline': '2099-12-31',
        'country': 'PRT',
        'cpv': '45223100-7',
        'value_numeric': 150000,
        'profile_score': 90,
        'title': 'Construção de estrutura metálica',
        'description': 'Empreitada de montagem de estruturas metálicas',
        'locations': [{'country': 'PRT', 'city': 'Leiria'}],
    }
    profile = {
        'countries': {'PRT'},
        'cities': {'LEIRIA'},
        'postal_prefixes': {'24'},
        'cpv_prefixes': ['45'],
        'min_value': 100000,
        'max_value': 300000,
        'services': ['estruturas metálicas'],
        'capability_tags': ['construção'],
    }

    # Inject the profile through the module dependency in a controlled way.
    import funnel_integration
    original = funnel_integration.evaluate_row
    try:
        from opportunity_match_pipeline import evaluate_row
        funnel_integration.evaluate_row = lambda row: evaluate_row(row, profile)
        decision, _ = persist_and_classify(conn, item, True)
    finally:
        funnel_integration.evaluate_row = original

    assert decision == 'QUALIFIED'
    row = latest_decision(conn, 'TED', '2026-S-1000')
    assert row['features']['economic_fit']['status'] == 'FAVOURABLE'
    assert row['features']['geography']['reason'] == 'cidade prioritária'
    assert row['features']['capability_evidence']['matched'] is True
    assert row['features']['hard_capability_blockers'] == []


def test_persist_and_classify_marks_hard_capability_blocker():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_decision_table(conn)

    item = {
        'source': 'TED',
        'external_id': '2026-S-1001',
        'score': 90,
        'deadline': '2099-12-31',
        'country': 'PRT',
        'cpv': '45223100-7',
        'value_numeric': 150000,
        'profile_score': 90,
        'title': 'Construção de ponte metálica',
        'description': 'Empreitada de estruturas metálicas',
        'locations': [{'country': 'PRT', 'city': 'Leiria'}],
    }
    profile = {
        'countries': {'PRT'},
        'cities': {'LEIRIA'},
        'postal_prefixes': {'24'},
        'cpv_prefixes': ['45'],
        'min_value': 100000,
        'max_value': 300000,
        'hard_exclusions': ['ponte'],
    }

    import funnel_integration
    original = funnel_integration.evaluate_row
    try:
        from opportunity_match_pipeline import evaluate_row
        funnel_integration.evaluate_row = lambda row: evaluate_row(row, profile)
        decision, reason = persist_and_classify(conn, item, True)
    finally:
        funnel_integration.evaluate_row = original

    assert decision == 'REJECTED'
    assert reason == 'CAPABILITY_BLOCKER'
    row = latest_decision(conn, 'TED', '2026-S-1001')
    assert row['features']['hard_capability_blockers']
