"""Contract tests for the European TED ingestion layer."""
import app
import preload  # noqa: F401 - installs the production TED transport


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_fetch_ted_paginates_with_iteration_token(monkeypatch):
    calls = []
    pages = [
        {"notices": [{"publication-number": "00000001-2026"}], "iterationNextToken": "next-1"},
        {"notices": [{"publication-number": "00000002-2026"}], "iterationNextToken": None},
    ]

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return FakeResponse(pages[len(calls) - 1])

    import ted_client
    monkeypatch.setattr(ted_client.requests, "post", fake_post)
    monkeypatch.setattr(app, "TED_MAX_PAGES", 5)
    rows = app.fetch_ted()

    assert [r["publication-number"] for r in rows] == ["00000001-2026", "00000002-2026"]
    assert calls[0][1]["paginationMode"] == "ITERATION"
    assert "iterationNextToken" not in calls[0][1]
    assert calls[1][1]["iterationNextToken"] == "next-1"
    assert calls[0][1]["limit"] == 250


def test_normalize_ted_preserves_place_and_market():
    row = app.normalize_ted({
        "publication-number": "00000003-2026",
        "notice-title": {"eng": "Steel warehouse construction"},
        "description-proc": {"eng": "Construction of a metal structure"},
        "buyer-name": {"eng": "Public Buyer"},
        "buyer-country": "ESP",
        "classification-cpv": [{"code": "45223200", "label": "Metal structures"}],
        "publication-date": "2026-08-18",
        "place-of-performance-country-proc": "ESP",
        "place-of-performance-city-proc": "Madrid",
    })

    assert row["source"] == "TED"
    assert row["external_id"] == "00000003-2026"
    assert row["country"] == "ESP"
    assert row["market"] == "EU"
    assert "Madrid" in row["description"]
    assert "45223200" in row["cpv"] or "Metal structures" in row["cpv"]
    assert row["published_at"].startswith("2026-08-18")
