"""Opt-in runtime wiring for CanadaBuys incremental construction ingestion.

This module deliberately does not import ``preload`` or decide activation policy.
The composition root supplies the environment/customer gate. That preserves the
architectural invariant: source registry readiness never implies ingestion.
"""
from canada_buys import SOURCE, fetch_canadabuys_tenders
from incremental_runtime_plugin import install_incremental_source


def install_canadabuys_runtime(app_module, *, source_enabled, record_blocked):
    """Install the CanadaBuys wrapper exactly once behind the supplied opt-in gate."""
    if not callable(source_enabled) or not callable(record_blocked):
        raise TypeError("CanadaBuys runtime requires explicit gate and blocked-source callbacks")
    return install_incremental_source(
        app_module,
        source=SOURCE,
        fetch_incremental=fetch_canadabuys_tenders,
        source_enabled=source_enabled,
        record_blocked=record_blocked,
    )
