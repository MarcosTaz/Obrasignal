"""Runtime installation for the Latvia IUB incremental source."""
import app as _app
import preload as _preload

from incremental_runtime_plugin import install_incremental_source
from latvia_iub import fetch_iub_tenders


SOURCE = "LV_IUB"


def install():
    """Install LV_IUB exactly once; the registry gate still controls activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_iub_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
