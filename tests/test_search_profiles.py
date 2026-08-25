import json
import sqlite3

import pytest

from search_profiles import (
    CANONICAL_SORT,
    FILTER_SCHEMA_VERSION,
    SearchProfileError,
    SearchProfileNeedsUpdate,
    SearchProfileNotFound,
    create_search_profile,
    delete_search_profile,
    ensure_search_profile_table,
    get_search_profile,
    list_search_profiles,
    normalize_filters,
    update_search_profile,
)


def connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_search_profile_table(conn)
    conn.commit()
    return conn


def test_create_normalizes_supported_filters_and_duplicate_names_are_allowed():
    conn = connection()
    try:
        first = create_search_profile(
            conn,
            "account-a",
            name="  Pintura Lisboa  ",
            filters={"market": "pt", "country": "prt", "q": "  Pintura  ", "minscore": 60},
        )
        second = create_search_profile(conn, "account-a", name="Pintura Lisboa", filters={})
        assert first["name"] == "Pintura Lisboa"
        assert first["filters"] == {"market": "PT", "country": "PRT", "q": "pintura", "minscore": 60}
        assert first["filter_schema_version"] == FILTER_SCHEMA_VERSION
        assert first["profile_id"] != second["profile_id"]
        assert len(list_search_profiles(conn, "account-a")) == 2
    finally:
        conn.close()


def test_rejects_unknown_filters_unsafe_sort_bad_ranges_and_oversized_query():
    with pytest.raises(SearchProfileError):
        normalize_filters({"sql": "DROP TABLE tenders"})
    with pytest.raises(SearchProfileError):
        normalize_filters({"country": "Portugal"})
    with pytest.raises(SearchProfileError):
        normalize_filters({"minscore": 101})
    with pytest.raises(SearchProfileError):
        normalize_filters({"q": "x" * 241})

    conn = connection()
    try:
        with pytest.raises(SearchProfileError):
            create_search_profile(conn, "account-a", name="Unsafe", filters={}, sort="deadline; DROP TABLE tenders")
    finally:
        conn.close()


def test_only_one_default_profile_per_account_and_accounts_are_independent():
    conn = connection()
    try:
        a1 = create_search_profile(conn, "account-a", name="A1", filters={}, is_default=True)
        a2 = create_search_profile(conn, "account-a", name="A2", filters={}, is_default=True)
        b1 = create_search_profile(conn, "account-b", name="B1", filters={}, is_default=True)
        assert get_search_profile(conn, "account-a", a1["profile_id"])["is_default"] is False
        assert get_search_profile(conn, "account-a", a2["profile_id"])["is_default"] is True
        assert get_search_profile(conn, "account-b", b1["profile_id"])["is_default"] is True
    finally:
        conn.close()


def test_tenant_scoping_hides_other_accounts_profile():
    conn = connection()
    try:
        profile = create_search_profile(conn, "account-a", name="Private", filters={})
        with pytest.raises(SearchProfileNotFound):
            get_search_profile(conn, "account-b", profile["profile_id"])
        with pytest.raises(SearchProfileNotFound):
            update_search_profile(conn, "account-b", profile["profile_id"], {"name": "Hijacked"})
        assert get_search_profile(conn, "account-a", profile["profile_id"])["name"] == "Private"
    finally:
        conn.close()


def test_old_schema_profile_is_marked_invalid_and_run_fails_closed():
    conn = connection()
    try:
        profile = create_search_profile(conn, "account-a", name="Old", filters={"q": "roof"})
        conn.execute(
            "UPDATE search_profiles SET filter_schema_version=? WHERE profile_id=?",
            (FILTER_SCHEMA_VERSION - 1, profile["profile_id"]),
        )
        conn.commit()

        observed = get_search_profile(conn, "account-a", profile["profile_id"])
        assert observed["status"] == "INVALID"
        with pytest.raises(SearchProfileNeedsUpdate):
            get_search_profile(conn, "account-a", profile["profile_id"], require_runnable=True)

        repaired = update_search_profile(
            conn,
            "account-a",
            profile["profile_id"],
            {"filters": {"q": "roofing"}, "sort": CANONICAL_SORT},
        )
        assert repaired["status"] == "ACTIVE"
        assert repaired["filter_schema_version"] == FILTER_SCHEMA_VERSION
    finally:
        conn.close()


def test_corrupt_stored_filter_is_not_silently_ignored():
    conn = connection()
    try:
        profile = create_search_profile(conn, "account-a", name="Corrupt", filters={})
        conn.execute(
            "UPDATE search_profiles SET filters_json=? WHERE profile_id=?",
            (json.dumps({"unsupported_operator": {"$regex": ".*"}}), profile["profile_id"]),
        )
        conn.commit()
        observed = get_search_profile(conn, "account-a", profile["profile_id"])
        assert observed["status"] == "INVALID"
        with pytest.raises(SearchProfileNeedsUpdate):
            get_search_profile(conn, "account-a", profile["profile_id"], require_runnable=True)
    finally:
        conn.close()


def test_normal_crud_paths_execute_no_schema_ddl():
    conn = connection()
    statements = []
    conn.set_trace_callback(statements.append)
    try:
        created = create_search_profile(conn, "account-a", name="No DDL", filters={"market": "PT"})
        list_search_profiles(conn, "account-a")
        get_search_profile(conn, "account-a", created["profile_id"])
        update_search_profile(conn, "account-a", created["profile_id"], {"name": "Still no DDL"})
        delete_search_profile(conn, "account-a", created["profile_id"])
    finally:
        conn.close()
    assert not any(statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ")) for statement in statements)
