"""Runtime installation for Poland BZP incremental ingestion."""
import app as _app
import preload as _preload

from incremental_runtime_plugin import install_incremental_source
from poland_bzp import fetch_poland_bzp_tenders


SOURCE = "PL_BZP"


def install():
    """Install PL_BZP exactly once; registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_poland_bzp_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
