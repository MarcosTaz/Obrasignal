import sqlite3


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tenders (id INTEGER PRIMARY KEY, source TEXT, external_id TEXT, score INTEGER, title TEXT, description TEXT, buyer TEXT, cpv TEXT, deadline TEXT, publication_date TEXT)")
    conn.execute("CREATE TABLE opportunity_decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, source TEXT, external_id TEXT, decision TEXT, reason TEXT, score INTEGER, features_json TEXT, rule_version TEXT, decided_at TEXT)")
    conn.execute("INSERT INTO tenders VALUES (1,'TED','X-1',80,'Estruturas','Fabrico e montagem','Buyer','45213200',NULL,'2026-08-18')")
    conn.commit()
    return conn


def test_latest_decision_query_is_account_scoped():
    from decision_log import latest_decision

    conn = _conn()
    conn.execute("INSERT INTO opportunity_decisions(account_id,source,external_id,decision,reason,score,features_json,rule_version,decided_at) VALUES ('empresa-a','TED','X-1','QUALIFIED','encaixa',90,'{}','v1','2026-08-18T00:00:00Z')")
    conn.execute("INSERT INTO opportunity_decisions(account_id,source,external_id,decision,reason,score,features_json,rule_version,decided_at) VALUES ('empresa-b','TED','X-1','REVIEW','prazo',60,'{}','v1','2026-08-18T00:00:00Z')")
    conn.commit()

    a = latest_decision(conn, 'TED', 'X-1', account_id='empresa-a')
    b = latest_decision(conn, 'TED', 'X-1', account_id='empresa-b')

    assert a['decision'] == 'QUALIFIED'
    assert a['score'] == 90
    assert b['decision'] == 'REVIEW'
    assert b['score'] == 60
    conn.close()


def test_personalized_ranking_priority_is_deterministic():
    from api import _decision_priority

    assert _decision_priority('QUALIFIED') < _decision_priority('REVIEW') < _decision_priority('REJECT')
    assert _decision_priority(None) == 2
