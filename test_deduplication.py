"""Tests for stable opportunity identity across repeated ingestion."""
from opportunity_events import opportunity_key


def test_same_source_and_external_id_are_same_event():
    row = {"source": "TED", "external_id": "2026/S-123456"}
    assert opportunity_key(row) == opportunity_key(dict(row))


def test_different_external_ids_are_distinct():
    a = {"source": "TED", "external_id": "2026/S-123456"}
    b = {"source": "TED", "external_id": "2026/S-654321"}
    assert opportunity_key(a) != opportunity_key(b)
