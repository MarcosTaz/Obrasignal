"""Runtime composition for sources that belong to a canonical shared family.

Country modules keep source-specific transport configuration and normalization.
This module removes repeated runtime glue while enforcing that a source is
registered in ``shared_source_families`` before it can use the shared installer.
"""
from incremental_runtime_plugin import install_incremental_source
from shared_source_families import assert_shared_family_health, family_for_source


def install_shared_family_source(
    app_module,
    preload_module,
    *,
    source,
    fetch_incremental,
    installer=install_incremental_source,
):
    source = str(source or "").upper()
    if not source:
        raise ValueError("shared-family runtime source is required")
    if not callable(fetch_incremental):
        raise TypeError("shared-family incremental fetcher must be callable")

    family = family_for_source(source)
    if family is None:
        raise ValueError(f"source {source} is not registered in a shared source family")

    # CI normally catches registry drift before startup. Rechecking here keeps
    # runtime composition fail-closed if deployment receives mismatched code.
    assert_shared_family_health()

    return installer(
        app_module,
        source=source,
        fetch_incremental=fetch_incremental,
        source_enabled=preload_module._global_source_enabled,
        record_blocked=preload_module._record_blocked_global_source,
    )
