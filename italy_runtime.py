"""Runtime installation for Italy ANAC PVL incremental Works-tender ingestion."""
import app as _app
import preload as _preload

from incremental_runtime_plugin import install_incremental_source
from italy_anac_pvl import SOURCE, fetch_italy_anac_tenders


def install():
    """Install IT_ANAC once; registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_italy_anac_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
