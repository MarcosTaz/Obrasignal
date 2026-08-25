import sqlite3

from opportunity_change_history import (
    MAX_TEXT_CHARS,
    build_monitored_state,
    content_fingerprint,
    get_change_history,
    persist_change_observations,
)


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _record(**overrides):
    record = {
        "source": "TEST_SOURCE",
        "signal_type": "TENDER",
        "external_id": "opp-adversarial",
        "title": "Construction services",
        "deadline": "2026-09-10",
        "source_status": "OPEN",
    }
    record.update(overrides)
    return record


def test_mixed_naive_and_aware_deadlines_remain_persistable_without_false_direction():
    conn = _conn()
    persist_change_observations(conn, [_record(deadline="2026-09-10")], observed_at="2026-08-24T09:00:00Z")
    result = persist_change_observations(
        conn,
        [_record(deadline="2026-09-10T12:00:00Z")],
        observed_at="2026-08-25T09:00:00Z",
    )

    assert result["change_sets"] == 1
    item = get_change_history(conn, "TEST_SOURCE", "opp-adversarial")[0]
    assert item["changed_fields"] == ["deadline"]
    assert item["changes"][0]["detail"] is None


def test_large_case_insensitive_text_is_normalized_before_bounding_and_hashing():
    repetitions = (MAX_TEXT_CHARS // len("alpha ")) + 100
    title_a = ("Alpha " * repetitions).strip()
    title_b = ("  ALPHA   " * repetitions).strip()

    state_a = build_monitored_state(_record(title=title_a))
    state_b = build_monitored_state(_record(title=title_b))

    assert state_a["title"] == state_b["title"]
    assert state_a["title"].startswith("sha256:")
    assert content_fingerprint(state_a) == content_fingerprint(state_b)
