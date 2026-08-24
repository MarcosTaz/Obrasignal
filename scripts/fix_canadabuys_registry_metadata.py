from pathlib import Path

path = Path("source_registry.py")
text = path.read_text()
old = '''    "CA_CANADABUYS": _source(
        country="CAN",
        source_id="ca_canadabuys_tender_notices",
        kind="OFFICIAL_TENDER_CSV",
        access="public_new_open_csv",
        status="ready",
        priority=1,
        legal_reuse="GREEN",
        machine_access="VERIFIED",
        expected_refresh_minutes=120,
        stale_after_minutes=360,
        capabilities=("incremental_sync", "detail", "amendments", "lifecycle"),
        signal_types=("TENDER",),
        wave=1,
        adapter="CanadaBuysConnector",
        realtime_capable=True,
    ),
'''
new = '''    "CA_CANADABUYS": _source(
        country="CAN",
        source_id="ca_canadabuys_tender_notices",
        kind="OFFICIAL_PUBLIC_CSV_DELTA_SNAPSHOT",
        access="public_new_open_complete_csv",
        status="ready",
        priority=1,
        legal_reuse="GREEN",
        machine_access="VERIFIED",
        expected_refresh_minutes=120,
        stale_after_minutes=2880,
        capabilities=("incremental_sync", "amendments", "lifecycle"),
        signal_types=("TENDER",),
        wave=1,
        adapter="CanadaBuysConnector",
        realtime_capable=False,
    ),
'''
if old not in text:
    raise SystemExit("expected CanadaBuys registry block not found")
if text.count(old) != 1:
    raise SystemExit("CanadaBuys registry block is not unique")
path.write_text(text.replace(old, new, 1))
