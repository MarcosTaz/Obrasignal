import sqlite3
import threading

from pursuit_decision import (
    current_decision,
    ensure_pursuit_decision_table,
    record_pursuit_decision,
)


def _connect(path):
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def test_concurrent_decisions_serialize_to_one_supersession_tip(tmp_path):
    """Two valid concurrent commands must not create two valid current states."""
    path = tmp_path / "pursuit-concurrency.db"
    conn = _connect(path)
    ensure_pursuit_decision_table(conn)
    conn.close()

    barrier = threading.Barrier(3)
    results = []
    errors = []
    lock = threading.Lock()

    def worker(state):
        local = _connect(path)
        try:
            barrier.wait()
            decision, created = record_pursuit_decision(
                local,
                account_id="tenant-a",
                opportunity_id=77,
                decision_type=state,
                idempotency_key=f"concurrent-{state.lower()}",
            )
            with lock:
                results.append((decision, created))
        except Exception as exc:  # expose any lock/fork failure deterministically
            with lock:
                errors.append(exc)
        finally:
            local.close()

    threads = [
        threading.Thread(target=worker, args=("PURSUE",)),
        threading.Thread(target=worker, args=("NO_BID",)),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads), "concurrent transition deadlock"
    assert errors == []
    assert len(results) == 2
    assert all(created is True for _, created in results)

    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT decision_id, supersedes_decision_id FROM opportunity_pursuit_decisions "
            "WHERE account_id='tenant-a' AND opportunity_id=77 ORDER BY id"
        ).fetchall()
        tips = conn.execute(
            """SELECT d.decision_id FROM opportunity_pursuit_decisions d
               WHERE d.account_id='tenant-a' AND d.opportunity_id=77
                 AND NOT EXISTS (
                     SELECT 1 FROM opportunity_pursuit_decisions n
                     WHERE n.account_id=d.account_id
                       AND n.supersedes_decision_id=d.decision_id
                 )"""
        ).fetchall()
        current = current_decision(conn, "tenant-a", 77)
    finally:
        conn.close()

    assert len(rows) == 2
    assert rows[0]["supersedes_decision_id"] is None
    assert rows[1]["supersedes_decision_id"] == rows[0]["decision_id"]
    assert len(tips) == 1
    assert current["decision_id"] == tips[0]["decision_id"]
