"""Runtime installation for France DECP construction-contract ingestion.

BOAMP remains the existing France tender-discovery source.  This runtime adds the
second member of the canonical BOAMP/DECP family and persists DECP only through
the canonical Signal path because DECP observations are CONTRACT signals.
"""
import app as _app
import preload as _preload

from france_decp import SOURCE, fetch_france_decp_contracts
from incremental_runtime_plugin import install_incremental_source


def install():
    """Install FR_DECP once; source registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_france_decp_contracts,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
