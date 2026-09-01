from datetime import datetime, timedelta, timezone

import pytest

from cloud_switching.estate import EstateAsset, EstateCertainty, InfrastructureEstate

NOW = datetime(2026, 8, 28, 20, 0, tzinfo=timezone.utc)


def asset(asset_id: str, **overrides):
    values = dict(
        asset_id=asset_id,
        asset_type="vm",
        cpu_cores=4,
        memory_gib=16,
        storage_gib=200,
        last_seen_at=NOW - timedelta(days=1),
        certainty=EstateCertainty.KNOWN,
        source_id="inventory-export",
    )
    values.update(overrides)
    return EstateAsset(**values)


def test_clean_estate_is_decision_ready():
    estate = InfrastructureEstate("tenant-a", [asset("vm-1"), asset("host-1", asset_type="host")])
    result = estate.assess(as_of=NOW)
    assert result.total_assets == 2
    assert result.vm_count == 1
    assert result.host_count == 1
    assert result.decision_ready


def test_duplicate_asset_fails_closed_instead_of_double_counting_vm():
    estate = InfrastructureEstate("tenant-a", [asset("vm-1"), asset("vm-1")])
    with pytest.raises(ValueError, match="duplicate asset_id"):
        estate.assess(as_of=NOW)


def test_stale_inventory_blocks_decision_readiness():
    estate = InfrastructureEstate(
        "tenant-a",
        [asset("vm-old", last_seen_at=NOW - timedelta(days=45))],
    )
    result = estate.assess(as_of=NOW, stale_after_days=30)
    assert result.stale_asset_ids == ("vm-old",)
    assert not result.decision_ready


def test_unknown_asset_blocks_decision_readiness():
    estate = InfrastructureEstate(
        "tenant-a",
        [asset("vm-unknown", certainty=EstateCertainty.UNKNOWN, source_id=None)],
    )
    result = estate.assess(as_of=NOW)
    assert result.unknown_asset_ids == ("vm-unknown",)
    assert not result.decision_ready


def test_missing_capacity_blocks_decision_readiness():
    estate = InfrastructureEstate("tenant-a", [asset("vm-1", storage_gib=None)])
    result = estate.assess(as_of=NOW)
    assert result.missing_capacity_asset_ids == ("vm-1",)
    assert not result.decision_ready


def test_future_last_seen_is_rejected():
    estate = InfrastructureEstate("tenant-a", [asset("vm-future", last_seen_at=NOW + timedelta(days=1))])
    with pytest.raises(ValueError, match="future"):
        estate.assess(as_of=NOW)
