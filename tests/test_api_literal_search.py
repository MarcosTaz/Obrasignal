"""Offline HTTP and SQLite regression tests for bounded literal radar search."""
import random
import sqlite3

import pytest

import app
import api


@pytest.fixture
def radar_client(tmp_path, monkeypatch):
    path = str(tmp_path / "radar-search.db")
    monkeypatch.setenv("OBRASIGNAL_DB", path)
    monkeypatch.setenv("OBRASIGNAL_AUTH_MODE", "development")
    monkeypatch.setenv("OBRASIGNAL_ACCOUNT_ID", "account-a")
    monkeypatch.setattr(app, "DB", path)
    app.init_db()
    conn = app.db()
    rows = (
        ("A-PCT", "Estruturas 100% metal", 91, "account-a"),
        ("A-UND", "Concurso beta_2", 85, "account-a"),
        ("A-BSL", r"Projeto pasta\sub", 80, "account-a"),
        ("A-NORM", "Reabilitação municipal", 75, "account-a"),
        ("B-PCT", "Privado 100% metal", 99, "account-b"),
    )
    for external_id, title, score, account in rows:
        conn.execute(
            """INSERT INTO tenders(source, external_id, title, description,
               buyer, country, cpv, deadline, score, first_seen)
               VALUES('TED', ?, ?, '', '', 'PRT', '45210000', '2099-01-01', ?, '2026-10-01')""",
            (external_id, title, score),
        )
        conn.execute(
            """INSERT INTO opportunity_decisions(
               account_id, source, external_id, decision, reason, score,
               features_json, rule_version, decided_at)
               VALUES(?, 'TED', ?, 'QUALIFIED', 'fixture', ?, '{}', 'fixture',
                      '2026-10-01T00:00:00Z')""",
            (account, external_id, score),
        )
    conn.commit()
    conn.close()
    return api.APP.test_client()


@pytest.mark.parametrize(("query", "expected"), [
    ("%", ["A-PCT"]),
    ("_", ["A-UND"]),
    ("\\", ["A-BSL"]),
    ("metal", ["A-PCT"]),
    ("municipal", ["A-NORM"]),
    ("not-existing", []),
])
def test_radar_search_treats_wildcards_as_literal_characters(radar_client, query, expected):
    result = radar_client.get("/api/v1/opportunities", query_string={"q": query})
    assert result.status_code == 200, result.get_json()
    assert [item["external_id"] for item in result.get_json()["items"]] == expected


@pytest.mark.parametrize(("parameter", "value"), [
    ("q", "a" * 257),
    ("source", "T" * 65),
    ("country", "P" * 9),
    ("market", "E" * 9),
])
def test_radar_rejects_oversized_filters_before_database_search(radar_client, parameter, value):
    result = radar_client.get("/api/v1/opportunities", query_string={parameter: value})
    assert result.status_code == 400
    assert result.get_json()["error"] == "invalid_query"


def test_sqlite_like_escape_is_exact_for_512_adversarial_strings():
    rng = random.Random(20261030)
    alphabet = "abc123%_\\"
    conn = sqlite3.connect(":memory:")
    for _ in range(512):
        value = "".join(rng.choice(alphabet) for __ in range(rng.randrange(1, 19)))
        escaped = api._literal_like(value)
        assert conn.execute(
            "SELECT ? LIKE ? ESCAPE '\\'", (value, escaped)
        ).fetchone()[0] == 1
        decoy = value + "Z"
        assert conn.execute(
            "SELECT ? LIKE ? ESCAPE '\\'", (decoy, escaped)
        ).fetchone()[0] == 0
    conn.close()
