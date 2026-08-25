"""Runtime installation for Estonia RHR eForms monthly open-data ingestion."""
import app as _app
import preload as _preload

from estonia_rhr import fetch_estonia_rhr_tenders
from shared_family_runtime import install_shared_family_source


SOURCE = "EE_RHR"


def install():
    """Install EE_RHR exactly once; registry + env still control activation."""
    return install_shared_family_source(
        _app,
        _preload,
        source=SOURCE,
        fetch_incremental=fetch_estonia_rhr_tenders,
    )
