"""Runtime installation for Brazil PNCP construction procurement-plan signals."""
import app as _app
import preload as _preload

from brazil_pncp_pca import SOURCE, fetch_brazil_pncp_pca_plans
from incremental_runtime_plugin import install_incremental_source


def install():
    """Install BR_PNCP_PCA once; registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_brazil_pncp_pca_plans,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
