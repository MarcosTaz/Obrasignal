from account_privacy import account_data_inventory
from decision_refresh import ensure_decision_input_table
from push_runtime import ensure_push_schema


def test_production_account_schema_has_no_unclassified_tenant_data(monkeypatch, tmp_path):
    import app

    path = tmp_path / "privacy-contract.db"
    monkeypatch.setattr(app, "DB", str(path))
    monkeypatch.setenv("OBRASIGNAL_DB", str(path))
    app.init_db()

    conn = app.db()
    try:
        # These two feature schemas are completed synchronously by cors_app in
        # production after the core app migration and before workers start.
        ensure_push_schema(conn)
        ensure_decision_input_table(conn)
        conn.commit()
        inventory = account_data_inventory(conn)
        assert inventory["missing"] == []
        assert inventory["unknown"] == []
    finally:
        conn.close()
