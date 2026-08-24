"""Runtime installation for Ecuador SERCOP monthly OCDS ingestion."""
import app as _app
import preload as _preload

from ecuador_sercop import fetch_sercop_tenders
from incremental_runtime_plugin import install_incremental_source


SOURCE = "EC_SERCOP"


def install():
    """Install EC_SERCOP exactly once; registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_sercop_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
