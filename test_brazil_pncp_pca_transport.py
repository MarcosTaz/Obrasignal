import pytest
import requests

import brazil_pncp_pca as br


class _Response:
    def __init__(self, *, content=b"{}", payload=None, status_code=200):
        self.content = content
        self._payload = {"ok": True} if payload is None else payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


def test_empty_body_is_only_success_when_caller_explicitly_allows_it(monkeypatch):
    calls = []
    sleeps = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        return _Response(content=b"")

    monkeypatch.setattr(br.requests, "get", fake_get)
    monkeypatch.setattr(br.time, "sleep", sleeps.append)

    assert br._request_json("https://example.invalid/items", allow_empty=True) is None
    assert len(calls) == 1
    assert sleeps == []


def test_empty_body_remains_fail_closed_for_discovery_and_identity_endpoints(monkeypatch):
    calls = []
    sleeps = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        return _Response(content=b"")

    monkeypatch.setattr(br.requests, "get", fake_get)
    monkeypatch.setattr(br.time, "sleep", sleeps.append)

    with pytest.raises(RuntimeError, match="request failed after bounded retries"):
        br._request_json("https://example.invalid/search")

    assert len(calls) == br.HTTP_MAX_ATTEMPTS == 5
    assert sleeps == [1, 2, 4, 8]


def test_remote_disconnect_uses_bounded_backoff_and_can_recover_on_final_attempt(monkeypatch):
    attempts = []
    sleeps = []

    def fake_get(*args, **kwargs):
        attempts.append(1)
        if len(attempts) < br.HTTP_MAX_ATTEMPTS:
            raise requests.ConnectionError("remote closed")
        return _Response(payload={"recovered": True})

    monkeypatch.setattr(br.requests, "get", fake_get)
    monkeypatch.setattr(br.time, "sleep", sleeps.append)

    assert br._request_json("https://example.invalid/search") == {"recovered": True}
    assert len(attempts) == 5
    assert sleeps == [1, 2, 4, 8]


def test_category_items_interprets_live_proven_empty_success_as_zero_matches(monkeypatch):
    calls = []

    def fake_request(url, *, params=None, allow_empty=False):
        calls.append((dict(params or {}), allow_empty))
        return None

    monkeypatch.setattr(br, "_request_json", fake_request)

    assert br._category_items("08241804000194", "2026", "1", "3") == []
    assert calls == [(
        {"categoria": "3", "pagina": 1, "tamanhoPagina": br.ITEM_PAGE_SIZE},
        True,
    )]
