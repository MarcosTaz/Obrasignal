"""Opt-in runtime wiring for the CanadaBuys connector."""
from canada_buys import SOURCE, fetch_canadabuys_tenders
from incremental_runtime_plugin import install_incremental_source
from source_registry import production_gate_reasons


def install_canadabuys_runtime(app_module, *, record_blocked):
    """Install CanadaBuys only when the source registry production gate passes."""
    return install_incremental_source(
        app_module,
        source=SOURCE,
        fetch_incremental=fetch_canadabuys_tenders,
        source_enabled=lambda name: not production_gate_reasons(name),
        record_blocked=record_blocked,
    )
