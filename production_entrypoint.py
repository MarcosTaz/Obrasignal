"""Production WSGI entrypoint.

`cors_app` owns the complete synchronous startup boundary: core and account-
private schema, SQLite WAL hardening, incremental decision recorder selection,
read models and source runtimes are installed before either background worker is
started. Keeping this entrypoint intentionally thin prevents a worker from
running with a temporary/legacy implementation while import-time patches are
still being applied.
"""
from cors_app import APP
