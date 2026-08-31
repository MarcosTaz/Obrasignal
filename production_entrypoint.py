"""Production WSGI entrypoint with schema migrations removed from request hot paths.

`cors_app` owns the startup migration boundary and completes the core schema
before this module returns. Production patches below are installed at startup,
before the first source poll can reach its decision phase, so request hot paths
never perform DDL and source observations do not repeatedly rewrite unchanged
account decisions.
"""
from cors_app import APP
import push_runtime as _push_runtime
import preload as _preload
from app import db as _db
from decision_refresh import ensure_decision_input_table, record_account_decisions


def _schema_already_initialized(_conn) -> None:
    """Production no-op: the push schema was migrated synchronously by cors_app."""
    return None


# Finish the incremental decision-refresh schema at the startup boundary. This
# table stores only hashes of public opportunity inputs + account profile state.
_decision_conn = _db()
try:
    ensure_decision_input_table(_decision_conn)
    _decision_conn.commit()
finally:
    _decision_conn.close()

# These names are resolved at call time by the running schedulers. Unit tests
# still exercise the real migration/legacy functions when importing their
# modules directly; production uses the startup-prepared schema and incremental
# account decision refresh.
_push_runtime.ensure_push_schema = _schema_already_initialized
_preload._record_account_decisions = record_account_decisions
