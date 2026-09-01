import sqlite3


def test_push_schema_fastpath_is_read_only_when_ready_and_migrates_fresh_db():
    import push_runtime
    from push_schema_fastpath import install, schema_ready

    original = push_runtime.ensure_push_schema
    try:
        install(push_runtime)
        fresh = sqlite3.connect(":memory:")
        fresh.row_factory = sqlite3.Row
        assert schema_ready(fresh) is False
        push_runtime.ensure_push_schema(fresh)
        assert schema_ready(fresh) is True

        statements = []
        fresh.set_trace_callback(statements.append)
        push_runtime.ensure_push_schema(fresh)
        fresh.set_trace_callback(None)
        writes = [
            sql for sql in statements
            if sql.lstrip().upper().startswith(("CREATE ", "ALTER ", "INSERT ", "UPDATE ", "DELETE ", "BEGIN ", "COMMIT"))
        ]
        assert writes == []
        fresh.close()
    finally:
        push_runtime.ensure_push_schema = original
