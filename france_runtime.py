"""Opt-in runtime wiring for France DECP construction-contract ingestion.

BOAMP remains the existing France tender-discovery source. This module adds the
second member of the canonical BOAMP/DECP family without importing ``preload`` or
choosing activation policy itself. The composition root supplies the gate, exactly
like other incremental global sources.
"""
from france_decp import SOURCE, fetch_france_decp_contracts
from incremental_runtime_plugin import install_incremental_source


def install_france_decp_runtime(app_module, *, source_enabled, record_blocked):
    """Install FR_DECP once behind the supplied production/source opt-in gate."""
    if not callable(source_enabled) or not callable(record_blocked):
        raise TypeError("France DECP runtime requires explicit gate and blocked-source callbacks")
    return install_incremental_source(
        app_module,
        source=SOURCE,
        fetch_incremental=fetch_france_decp_contracts,
        source_enabled=source_enabled,
        record_blocked=record_blocked,
    )
