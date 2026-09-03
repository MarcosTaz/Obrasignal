from __future__ import annotations

from factory_cloud.shared_contracts import ReleaseEvidence

REQUIRED_CHECKS = ("python", "mobile")


def release_ready(*, revision: str, successful_checks: tuple[str, ...]) -> bool:
    evidence = ReleaseEvidence.create(
        revision=revision,
        required_checks=REQUIRED_CHECKS,
        successful_checks=successful_checks,
    )
    evidence.require_ready()
    return True
