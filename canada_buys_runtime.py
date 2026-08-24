"""Runtime installation for CanadaBuys incremental construction ingestion."""
import app as _app
import preload as _preload

from canada_buys import SOURCE, fetch_canadabuys_tenders
from incremental_runtime_plugin import install_incremental_source


def install():
    """Install CA_CANADABUYS exactly once; registry + env control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_canadabuys_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
