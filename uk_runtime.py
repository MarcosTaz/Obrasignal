"""Runtime installation for UK Find a Tender incremental OCDS ingestion."""
import app as _app
import preload as _preload

from shared_family_runtime import install_shared_family_source
from uk_find_tender import fetch_uk_tenders


SOURCE = "UK_PROCUREMENT"


def install():
    """Install UK_PROCUREMENT exactly once; registry + env still control activation."""
    return install_shared_family_source(
        _app,
        _preload,
        source=SOURCE,
        fetch_incremental=fetch_uk_tenders,
    )
