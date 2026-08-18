import preload  # noqa: F401 - installs the production TED transport
import app


def test_fetch_ted_retries_transient_http_failure(monkeypatch):
    calls = []

    class Response:
        def __init__(self, status=200):
            self.status_code = status
        def raise_for_status(self):
            if self.status_code >= 500:
                raise RuntimeError("temporary TED failure")
        def json(self):
            return {"notices": [{"publication-number": "1-2026"}]}

    def fake_post(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            return Response(503)
        return Response()

    # Patch the underlying transport used by ted_client without bypassing
    # the retry wrapper installed by preload.
    import ted_client
    monkeypatch.setattr(ted_client.requests, "post", fake_post)
    monkeypatch.setattr(app, "TED_MAX_PAGES", 1)
    monkeypatch.setattr(ted_client.time, "sleep", lambda *_: None)

    rows = app.fetch_ted()
    assert rows == [{"publication-number": "1-2026"}]
    assert len(calls) == 2


def test_fetch_ted_stops_when_iteration_token_disappears(monkeypatch):
    responses = iter([
        {"notices": [{"publication-number": "1-2026"}], "iterationNextToken": "next"},
        {"notices": [{"publication-number": "2-2026"}]},
    ])
    seen_bodies = []

    class Response:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            pass
        def json(self):
            return self.payload

    def fake_post(*args, **kwargs):
        seen_bodies.append(kwargs["json"])
        return Response(next(responses))

    import ted_client
    monkeypatch.setattr(ted_client.requests, "post", fake_post)

    rows = app.fetch_ted()
    assert [r["publication-number"] for r in rows] == ["1-2026", "2-2026"]
    assert seen_bodies[1]["iterationNextToken"] == "next"
