"""Runtime installation for credential-gated Korea KONEPS construction tenders."""
import app as _app
import preload as _preload

from incremental_runtime_plugin import install_incremental_source
from korea_koneps import SOURCE, fetch_korea_koneps_tenders


def install():
    """Install KR_KONEPS once; registry + env continue to control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_korea_koneps_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
