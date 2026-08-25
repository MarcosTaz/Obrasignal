"""Runtime installation for UK Find a Tender incremental OCDS ingestion."""
import app as _app
import preload as _preload

from shared_family_runtime import install_shared_family_source
from uk_find_tender_lifecycle import fetch_uk_lifecycle_signals


SOURCE = "UK_PROCUREMENT"

# Preserve the existing source-runtime public seam used by deterministic tests and
# integration tooling. The implementation now returns canonical lifecycle signals,
# but callers do not need a country-specific runtime API migration.
fetch_uk_tenders = fetch_uk_lifecycle_signals


def install():
    """Install UK_PROCUREMENT exactly once; registry + env still control activation."""
    return install_shared_family_source(
        _app,
        _preload,
        source=SOURCE,
        fetch_incremental=fetch_uk_tenders,
    )
