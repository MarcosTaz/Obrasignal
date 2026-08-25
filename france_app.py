"""Production composition root adding France DECP behind the existing source gate.

The public WSGI application remains ``cors_app.APP``.  Importing that application
first preserves all existing preload/API wiring; the DECP incremental wrapper is
then installed additively and is still inert unless ``FR_DECP`` is explicitly
listed in ``OBRASIGNAL_GLOBAL_SOURCES`` and its registry gate passes.
"""
from cors_app import APP
import preload as _preload

from france_runtime import install_france_decp_runtime


install_france_decp_runtime(
    _preload._app,
    source_enabled=_preload._global_source_enabled,
    record_blocked=_preload._record_blocked_global_source,
)

__all__ = ["APP"]
