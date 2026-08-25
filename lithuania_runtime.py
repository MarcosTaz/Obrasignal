"""Runtime installation for Lithuania CVP IS complete-snapshot ingestion."""
import app as _app
import preload as _preload

from incremental_runtime_plugin import install_incremental_source
from lithuania_vpt import SOURCE, fetch_lithuania_vpt_tenders


def install():
    """Install LT_VPT exactly once; registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_lithuania_vpt_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
