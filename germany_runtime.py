"""Runtime installation for Germany DOE OpenData eForms ingestion."""
import app as _app
import preload as _preload

from germany_doe import SOURCE, fetch_germany_doe_tenders
from shared_family_runtime import install_shared_family_source


def install():
    """Install SERVICE_BUND_DE once; registry + env still control activation."""
    return install_shared_family_source(
        _app,
        _preload,
        source=SOURCE,
        fetch_incremental=fetch_germany_doe_tenders,
    )
