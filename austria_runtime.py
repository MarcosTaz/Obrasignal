"""Runtime installation for Austria Kerndaten/eForms incremental ingestion."""
import app as _app
import preload as _preload

from austria_kerndaten_incremental import fetch_austria_kerndaten_tenders
from incremental_runtime_plugin import install_incremental_source


SOURCE = "AT_KERNDATEN"


def install():
    """Install AT_KERNDATEN exactly once; registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_austria_kerndaten_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
