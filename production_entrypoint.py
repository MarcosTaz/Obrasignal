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

Production also makes the API OPTIONS fast-path the first global Flask hook.
Several guards are registered transitively while `api` is imported; without this
explicit ordering, a protected endpoint preflight could authenticate or open
SQLite before the CORS short-circuit even though `cors_app` defines a preflight
handler of its own.
"""
from cors_app import APP, _global_api_preflight
from runtime_auth_warm import warm_production_auth


_global_hooks = APP.before_request_funcs.setdefault(None, [])
if _global_api_preflight in _global_hooks:
    _global_hooks.remove(_global_api_preflight)
_global_hooks.insert(0, _global_api_preflight)

AUTH_WARM_STATE = warm_production_auth()
