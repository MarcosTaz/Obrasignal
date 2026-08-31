"""Production WSGI entrypoint with schema migrations removed from request hot paths.

`cors_app` owns the startup migration boundary and completes the push schema before
this module returns.  After that boundary, push requests and the scheduler must
never attempt DDL against the live SQLite database: long ingestion transactions
can otherwise turn a harmless status read into a 15-second lock timeout/HTTP 500.
"""
from cors_app import APP
import push_runtime as _push_runtime


def _schema_already_initialized(_conn) -> None:
    """Production no-op: the push schema was migrated synchronously by cors_app."""
    return None


# push_runtime resolves this name at call time.  Unit tests still exercise the
# real migration function because they import push_runtime directly; production
# request/scheduler paths use the already-migrated schema without runtime DDL.
_push_runtime.ensure_push_schema = _schema_already_initialized
