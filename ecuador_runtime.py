"""Runtime installation for Ecuador SERCOP monthly OCDS ingestion."""
import app as _app
import preload as _preload

from ecuador_sercop import fetch_sercop_tenders
from shared_family_runtime import install_shared_family_source


SOURCE = "EC_SERCOP"


def install():
    """Install EC_SERCOP exactly once; registry + env still control activation."""
    return install_shared_family_source(
        _app,
        _preload,
        source=SOURCE,
        fetch_incremental=fetch_sercop_tenders,
    )
