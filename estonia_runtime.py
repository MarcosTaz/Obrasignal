"""Runtime installation for Estonia RHR eForms monthly open-data ingestion."""
import app as _app
import preload as _preload

from estonia_rhr import fetch_estonia_rhr_tenders
from incremental_runtime_plugin import install_incremental_source


SOURCE = "EE_RHR"


def install():
    """Install EE_RHR exactly once; registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_estonia_rhr_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
