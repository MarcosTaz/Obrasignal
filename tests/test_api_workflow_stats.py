import sqlite3


def test_workflow_stats_is_account_scoped(monkeypatch):
    import api
    from opportunity_workflow import set_workflow

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    set_workflow(conn, "empresa-a", "TED", "X-1", "PREPARING")
    set_workflow(conn, "empresa-b", "TED", "X-2", "WON")

    class FakeApp:
        def db(self):
            return conn

    class Identity:
        account_id = "empresa-a"
        authenticated = True

    class RequestIdentity:
        obrasignal_identity = Identity()

    monkeypatch.setattr(api._preload, "_app", FakeApp())
    monkeypatch.setattr(api.request, "obrasignal_identity", Identity(), raising=False)

    counts = api.workflow_stats().get_json()["counts"]
    assert counts["PREPARING"] == 1
    assert counts["WON"] == 0
    assert counts["REVIEWING"] == 0
    conn.close()
