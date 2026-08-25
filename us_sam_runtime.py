"""Opt-in runtime wiring for SAM.gov federal construction ingestion."""
from us_sam import SOURCE, fetch_us_sam_tenders
from incremental_runtime_plugin import install_incremental_source


def install_us_sam_runtime(app_module, *, source_enabled, record_blocked):
    if not callable(source_enabled) or not callable(record_blocked):
        raise TypeError("SAM.gov runtime requires explicit gate and blocked-source callbacks")
    return install_incremental_source(
        app_module,
        source=SOURCE,
        fetch_incremental=fetch_us_sam_tenders,
        source_enabled=source_enabled,
        record_blocked=record_blocked,
    )
