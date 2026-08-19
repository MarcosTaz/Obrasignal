import sqlite3


def test_workflow_stats_uses_authenticated_account(monkeypatch):
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

    monkeypatch.setattr(api._preload, "_app", FakeApp())

    with api.APP.test_request_context("/api/v1/workflow/stats"):
        api.request.obrasignal_identity = Identity()
        response = api.workflow_stats()

    payload = response.get_json()

    assert payload["account_id"] == "empresa-a"
    assert payload["counts"]["PREPARING"] == 1
    assert payload["counts"]["WON"] == 0
    assert payload["counts"]["REVIEWING"] == 0
    conn.close()
