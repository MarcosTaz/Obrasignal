"""Runtime installation for Finland HILMA AVP national enrichment."""

import app as _app
import preload as _preload

from finland_hilma import SOURCE, fetch_finland_hilma
from incremental_runtime_plugin import install_incremental_source


def install():
    """Install FI_HILMA exactly once; registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_finland_hilma,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
