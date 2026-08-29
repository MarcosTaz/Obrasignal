from datetime import datetime, timezone
from decimal import Decimal as D

from cloud_switching.labour import ActivityCode, LabourEntry
from cloud_switching.labour_store import SQLiteLabourStore


def test_labour_entries_survive_reopen_and_summarize_by_case(tmp_path):
    path = tmp_path / "labour.db"
    store = SQLiteLabourStore(path)
    store.add(
        tenant_id="tenant-a",
        entry=LabourEntry(ActivityCode.ESTATE, D("1.0"), "pilot-1"),
        recorded_at=datetime(2026, 8, 29, 1, tzinfo=timezone.utc),
    )
    store.add(
        tenant_id="tenant-a",
        entry=LabourEntry(ActivityCode.BILLING, D("1.5"), "pilot-1"),
        recorded_at=datetime(2026, 8, 29, 2, tzinfo=timezone.utc),
    )
    store.add(
        tenant_id="tenant-a",
        entry=LabourEntry(ActivityCode.REWORK, D("0.5"), "pilot-1"),
        recorded_at=datetime(2026, 8, 29, 3, tzinfo=timezone.utc),
    )

    reopened = SQLiteLabourStore(path)
    summary = reopened.summarize_case(tenant_id="tenant-a", case_id="pilot-1", revenue=D("1500"))

    assert summary.total_hours == D("3.0")
    assert summary.rework_hours == D("0.5")
    assert summary.revenue_per_human_hour == D("500.00")


def test_labour_store_is_tenant_isolated(tmp_path):
    path = tmp_path / "labour.db"
    store = SQLiteLabourStore(path)
    store.add(
        tenant_id="tenant-a",
        entry=LabourEntry(ActivityCode.INTAKE, D("1"), "case-1"),
    )
    assert store.list_case(tenant_id="tenant-b", case_id="case-1") == []


def test_same_case_id_can_exist_for_two_tenants_without_leakage(tmp_path):
    path = tmp_path / "labour.db"
    store = SQLiteLabourStore(path)
    store.add(tenant_id="tenant-a", entry=LabourEntry(ActivityCode.INTAKE, D("1"), "shared"))
    store.add(tenant_id="tenant-b", entry=LabourEntry(ActivityCode.INTAKE, D("2"), "shared"))

    assert store.summarize_case(tenant_id="tenant-a", case_id="shared").total_hours == D("1")
    assert store.summarize_case(tenant_id="tenant-b", case_id="shared").total_hours == D("2")
