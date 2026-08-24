"""Runtime installation for Germany DOE OpenData eForms ingestion."""
import app as _app
import preload as _preload

from germany_doe import SOURCE, fetch_germany_doe_tenders
from incremental_runtime_plugin import install_incremental_source


def install():
    """Install SERVICE_BUND_DE once; registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_germany_doe_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
