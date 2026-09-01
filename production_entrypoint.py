"""Production WSGI entrypoint.

`cors_app` owns the complete synchronous startup boundary: core and account-
private schema, SQLite WAL hardening, incremental decision recorder selection,
read models and source runtimes are installed before either background worker is
started. Keeping this entrypoint thin prevents a worker from running with a
temporary/legacy implementation while import-time patches are still being
applied.

The public JWKS keyset is warmed before this module finishes importing. Gunicorn
does not serve the worker until import is complete, so the first authenticated
customer page cannot consume every request thread waiting behind provider key
discovery.
"""
from cors_app import APP
from runtime_auth_warm import warm_production_auth

AUTH_WARM_STATE = warm_production_auth()
