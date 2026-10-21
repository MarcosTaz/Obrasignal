"""Opt-in runtime wiring for the Zambia ZPPA OCDS public-works slice."""
from incremental_runtime_plugin import install_incremental_source
from zambia_zppa import SOURCE, fetch_zm_tenders


def install_zambia_zppa_runtime(app_module, *, source_enabled, record_blocked):
    """Install Zambia ingestion exactly once behind the composition-root gate."""
    if not callable(source_enabled) or not callable(record_blocked):
        raise TypeError("Zambia ZPPA runtime requires explicit gate and blocked-source callbacks")
    return install_incremental_source(
        app_module,
        source=SOURCE,
        fetch_incremental=fetch_zm_tenders,
        source_enabled=source_enabled,
        record_blocked=record_blocked,
    )
