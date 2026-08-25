import sqlite3

import pytest

from search_profiles import (
    SearchProfileNeedsUpdate,
    create_search_profile,
    ensure_search_profile_table,
    get_search_profile,
)


def test_malformed_persisted_json_is_invalid_and_never_runs_silently():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_search_profile_table(conn)
    profile = create_search_profile(conn, "account-a", name="Legacy", filters={"q": "roof"})
    conn.execute(
        "UPDATE search_profiles SET filters_json=? WHERE profile_id=?",
        ("{not-json", profile["profile_id"]),
    )
    conn.commit()

    observed = get_search_profile(conn, "account-a", profile["profile_id"])
    assert observed["status"] == "INVALID"
    with pytest.raises(SearchProfileNeedsUpdate):
        get_search_profile(conn, "account-a", profile["profile_id"], require_runnable=True)
    conn.close()
