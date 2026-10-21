from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Sequence


class EstateCertainty(str, Enum):
    KNOWN = "known"
    ESTIMATED = "estimated"
    ASSUMED = "assumed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EstateAsset:
    asset_id: str
    asset_type: str
    cpu_cores: Optional[int]
    memory_gib: Optional[int]
    storage_gib: Optional[int]
    last_seen_at: Optional[datetime]
    certainty: EstateCertainty
    source_id: Optional[str] = None

    def validate(self) -> None:
        if not self.asset_id.strip() or not self.asset_type.strip():
            raise ValueError("asset_id and asset_type are required")
        for field_name, value in (
            ("cpu_cores", self.cpu_cores),
            ("memory_gib", self.memory_gib),
            ("storage_gib", self.storage_gib),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{field_name} cannot be negative")
        if self.certainty is EstateCertainty.KNOWN and not self.source_id:
            raise ValueError("known estate asset requires source evidence")
        if self.last_seen_at is not None and self.last_seen_at.tzinfo is None:
            raise ValueError("last_seen_at must be timezone-aware")


@dataclass(frozen=True)
class EstateAssessment:
    total_assets: int
    vm_count: int
    host_count: int
    stale_asset_ids: tuple[str, ...]
    unknown_asset_ids: tuple[str, ...]
    missing_capacity_asset_ids: tuple[str, ...]
    decision_ready: bool


@dataclass(frozen=True)
class InfrastructureEstate:
    company_id: str
    assets: Sequence[EstateAsset]

    def assess(self, *, as_of: datetime, stale_after_days: int = 30) -> EstateAssessment:
        if not self.company_id.strip():
            raise ValueError("company_id is required")
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        as_of = as_of.astimezone(timezone.utc)
        if stale_after_days <= 0:
            raise ValueError("stale_after_days must be positive")
        if not self.assets:
            return EstateAssessment(0, 0, 0, (), (), (), False)

        seen = set()
        stale = []
        unknown = []
        missing_capacity = []
        vm_count = 0
        host_count = 0
        for asset in self.assets:
            asset.validate()
            if asset.asset_id in seen:
                raise ValueError(f"duplicate asset_id: {asset.asset_id}")
            seen.add(asset.asset_id)
            kind = asset.asset_type.strip().lower()
            if kind == "vm":
                vm_count += 1
            elif kind == "host":
                host_count += 1

            if asset.certainty is EstateCertainty.UNKNOWN:
                unknown.append(asset.asset_id)
            if asset.cpu_cores is None or asset.memory_gib is None or asset.storage_gib is None:
                missing_capacity.append(asset.asset_id)
            if asset.last_seen_at is None:
                stale.append(asset.asset_id)
            else:
                observed = asset.last_seen_at.astimezone(timezone.utc)
                age_days = (as_of - observed).total_seconds() / 86400
                if age_days < 0:
                    raise ValueError(f"asset {asset.asset_id} last_seen_at is in the future")
                if age_days > stale_after_days:
                    stale.append(asset.asset_id)

        decision_ready = not stale and not unknown and not missing_capacity
        return EstateAssessment(
            total_assets=len(self.assets),
            vm_count=vm_count,
            host_count=host_count,
            stale_asset_ids=tuple(sorted(stale)),
            unknown_asset_ids=tuple(sorted(unknown)),
            missing_capacity_asset_ids=tuple(sorted(missing_capacity)),
            decision_ready=decision_ready,
        )
