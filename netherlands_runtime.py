"""Runtime installation for Netherlands TenderNed public ingestion."""
import app as _app
import preload as _preload

from incremental_runtime_plugin import install_incremental_source
from netherlands_tenderned import SOURCE, fetch_tenderned_tenders


def install():
    """Install NL_TENDERNED exactly once; registry + env control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_tenderned_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
