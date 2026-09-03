import sqlite3


def test_bootstrap_reuses_profile_batches_writes_and_prefers_confirmed_open(monkeypatch):
    import account_onboarding as onboarding

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE tenders(
            id INTEGER PRIMARY KEY,
            source TEXT,
            external_id TEXT,
            title TEXT,
            description TEXT,
            cpv TEXT,
            deadline TEXT,
            publication_date TEXT,
            first_seen TEXT,
            score INTEGER,
            country TEXT
        )"""
    )
    conn.executemany(
        "INSERT INTO tenders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # This unknown-deadline row has the highest legacy score, but a
            # customer's default open-only Radar must not spend its bounded
            # first-value sample on it before confirmed-open work.
            (4, "TEST", "unknown", "Construction unknown", "Works", "45", None, "2098-12-04", "2098-12-04", 100, "PRT"),
            (1, "TEST", "a", "Construction A", "Works", "45", "2099-01-01", "2098-12-03", "2098-12-03", 90, "PRT"),
            (2, "TEST", "b", "Construction B", "Works", "45", "2099-01-02", "2098-12-02", "2098-12-02", 80, "PRT"),
            (3, "TEST", "c", "Construction C", "Works", "45", "2099-01-03", "2098-12-01", "2098-12-01", 70, "PRT"),
        ],
    )
    conn.commit()

    class NoClose:
        def __getattr__(self, name):
            return getattr(conn, name)

        def close(self):
            return None

    profile = {"account_id": "acct-a", "name": "A", "activity": "Construção"}
    profile_loads = []
    calls = []

    monkeypatch.setattr(onboarding, "db", lambda: NoClose())
    monkeypatch.setattr(
        onboarding,
        "load_profile",
        lambda account_id: profile_loads.append(account_id) or profile,
    )
    monkeypatch.setattr(onboarding, "_emit_bootstrap_events", lambda _conn, _account_id: 0)

    def fake_persist(_conn, item, is_new, account_id="default", supplied_profile=None, **kwargs):
        # Accept both the public keyword and kwargs so the assertion below
        # documents the exact batch contract without coupling to call order.
        effective_profile = kwargs.pop("profile", supplied_profile)
        calls.append((item["external_id"], is_new, account_id, effective_profile, kwargs))
        return "REVIEW", "ok"

    monkeypatch.setattr(onboarding, "persist_and_classify", fake_persist)

    assert onboarding.bootstrap_account("acct-a", limit=3) == 3
    assert profile_loads == ["acct-a"]
    assert [call[0] for call in calls] == ["a", "b", "c"]
    assert all(call[2] == "acct-a" for call in calls)
    assert all(call[3] is profile for call in calls)
    assert all(call[4]["commit"] is False for call in calls)
    assert all(call[4]["ensure"] is False for call in calls)
    assert all(isinstance(call[4].get("evaluation"), dict) for call in calls)
    assert all(call[4]["evaluation"].get("profile_score") is not None for call in calls)

    conn.close()
