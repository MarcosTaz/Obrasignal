"""Current-trust producer/consumer contract failing-before probes.

Observation-only. Data Contracts owns the compatibility invariant, while Mobile/Web
owners retain consumer implementation semantics.
"""
from pathlib import Path


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def test_unknown_source_is_no_longer_fabricated_as_ted_control():
    app = _read("mobile/App.js")
    assert "item.source||'TED'" not in app
    assert "current.source||'TED'" not in app
    assert "Fonte não identificada" in app


def test_profile_consumer_must_not_accept_envelope_or_flat_by_truthiness():
    api = _read("mobile/src/api.js")
    assert "function unwrapProfile(data){return data?.profile||data||null;}" not in api, (
        "PROFILE_CONTRACT_REVIEW_REQUIRED: current Mobile parser accepts canonical envelope, "
        "legacy flat objects and malformed truthy envelope shapes without an explicit contract"
    )


def test_stats_unknown_must_not_render_as_zero():
    app = _read("mobile/App.js")
    assert "{v??0}" not in app, (
        "UNKNOWN_TO_ZERO: missing/unknown stats are rendered as numeric zero"
    )


def test_opportunity_unknown_score_must_not_render_as_zero():
    app = _read("mobile/App.js")
    assert "item.decision_score??item.score??0" not in app, (
        "UNKNOWN_TO_ZERO: missing current decision score is rendered as 0"
    )


def test_opportunity_unknown_reason_must_not_become_positive_explanation():
    app = _read("mobile/App.js")
    assert "item.decision_reason||item.match_reason||'Correspondência com o perfil'" not in app, (
        "UNKNOWN_TO_POSITIVE_EXPLANATION: missing reason fabricates a positive profile-match explanation"
    )


def test_workflow_unknown_status_must_not_become_new():
    app = _read("mobile/App.js")
    assert "current.workflow?.status||'NEW'" not in app, (
        "UNKNOWN_TO_NEW: missing workflow status is rendered as NEW"
    )
