from zambia_zppa import fetch_zm_tenders


def test_zambia_zppa_live_snapshot_smoke():
    rows, cursor = fetch_zm_tenders()
    assert cursor
    assert isinstance(rows, list)
    for row in rows[:10]:
        assert row["source"] == "ZM_ZPPA"
        assert row["country"] == "ZMB"
        assert row["external_id"].startswith("ocds-23g63a")
        assert row["contract_type"].lower() == "works"
