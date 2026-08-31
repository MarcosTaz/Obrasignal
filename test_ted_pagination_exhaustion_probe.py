"""Resilience failing-before probe for TED partial pagination truth.

Diagnostic only. Source/TED owners retain fetch/cursor semantics.
"""

import pytest

import preload


def _notice(number="TED-PROBE-1"):
    return {
        "publication-number": number,
        "publication-date": "2026-08-25",
        "notice-title": "Pagination probe",
    }


def test_page_budget_with_natural_end_remains_complete(monkeypatch):
    monkeypatch.setattr(preload._app, "TED_MAX_PAGES", 1)
    monkeypatch.setattr(preload, "_ted_since_date", lambda: "20260801")

    calls = []

    def complete_response(*_args, **_kwargs):
        calls.append(1)
        return {"notices": [_notice()], "iterationNextToken": None}

    monkeypatch.setattr(preload, "post_json", complete_response)
    rows = preload._fetch_ted_resilient()
    assert len(calls) == 1
    assert [row["publication-number"] for row in rows] == ["TED-PROBE-1"]


def test_page_budget_exhaustion_with_continuation_token_is_not_complete(monkeypatch):
    monkeypatch.setattr(preload._app, "TED_MAX_PAGES", 1)
    monkeypatch.setattr(preload, "_ted_since_date", lambda: "20260801")

    calls = []

    def still_has_more(*_args, **_kwargs):
        calls.append(1)
        return {
            "notices": [_notice("TED-PARTIAL-1")],
            "iterationNextToken": "more-pages-remain",
        }

    monkeypatch.setattr(preload, "post_json", still_has_more)

    with pytest.raises(RuntimeError, match="(?i)(partial|incomplete|page|pagination|limit|budget)"):
        preload._fetch_ted_resilient()

    assert len(calls) == 1
