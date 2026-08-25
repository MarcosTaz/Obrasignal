"""Runtime installation for Switzerland SIMAP incremental ingestion."""
import app as _app
import preload as _preload

from incremental_runtime_plugin import install_incremental_source
from switzerland_simap import fetch_simap_tenders


SOURCE = "CH_SIMAP"


def install():
    """Install CH_SIMAP exactly once; registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_simap_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
