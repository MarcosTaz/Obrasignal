def test_new_tender_from_interrupted_sync_is_alerted_on_next_good_sync(monkeypatch, tmp_path):
    import app
    from decision_log import record_decision
    from notification_events import record_new_opportunities

    path = tmp_path / "failed-sync-alert.db"
    monkeypatch.setattr(app, "DB", str(path))
    app.init_db()
    conn = app.db()
    try:
        previous = "2026-09-01T00:00:00+00:00"
        interrupted_first_seen = "2026-09-01T00:05:00+00:00"
        current = "2026-09-01T00:10:00+00:00"
        conn.execute(
            "INSERT INTO sync_runs(started_at,finished_at,found,new_items) VALUES(?,?,0,0)",
            ("2026-08-31T23:59:00+00:00", previous),
        )
        # Auditable failed attempt: tender row was safely committed in a bounded
        # chunk but the run never reached its completion marker.
        conn.execute(
            "INSERT INTO sync_runs(started_at,finished_at,found,new_items) VALUES(?,NULL,0,0)",
            ("2026-09-01T00:04:00+00:00",),
        )
        conn.execute(
            """INSERT INTO tenders(
                source,external_id,title,description,buyer,country,cpv,value,deadline,
                publication_date,url,score,first_seen,last_seen,published_at,match_reason,
                priority_label,priority_class,market
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "TEST", "new-after-failure", "Bridge works", "construction", "Buyer", "PRT",
                "45200000", "100000", "2099-01-01", "2026-09-01", "https://example.invalid",
                90, interrupted_first_seen, current, interrupted_first_seen, "fit", "HIGH", "hot", "PT",
            ),
        )
        conn.execute(
            "INSERT INTO sync_runs(started_at,finished_at,found,new_items) VALUES(?,?,1,1)",
            ("2026-09-01T00:09:00+00:00", current),
        )
        conn.commit()
        record_decision(
            conn, "TEST", "new-after-failure", "QUALIFIED", "account fit", score=92,
            account_id="tenant-a",
        )

        events = record_new_opportunities(conn, account_id="tenant-a", min_score=75)
        assert len(events) == 1
        assert events[0]["account_id"] == "tenant-a"
        assert events[0]["score"] == 92

        # Canonical event identity keeps the recovery idempotent.
        assert record_new_opportunities(conn, account_id="tenant-a", min_score=75) == []
    finally:
        conn.close()
