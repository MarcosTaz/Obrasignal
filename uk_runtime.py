"""Runtime installation for UK Find a Tender incremental OCDS ingestion."""
import app as _app
import preload as _preload

from incremental_runtime_plugin import install_incremental_source
from uk_find_tender import fetch_uk_tenders


SOURCE = "UK_PROCUREMENT"


def install():
    """Install UK_PROCUREMENT exactly once; registry + env still control activation."""
    return install_incremental_source(
        _app,
        source=SOURCE,
        fetch_incremental=fetch_uk_tenders,
        source_enabled=_preload._global_source_enabled,
        record_blocked=_preload._record_blocked_global_source,
    )
