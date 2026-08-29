from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from factory_cloud.pilot_contract import load_pilot_contract

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class PilotReadinessError(RuntimeError):
    pass


@dataclass(frozen=True)
class PilotReadinessEvidence:
    vertical: str
    source_registered: bool
    deterministic_core: bool
    evidence_lineage: bool
    tenant_isolation: bool
    durable_recovery: bool
    adversarial_tests: bool
    delivery_economics_defined: bool
    onboarding_exit_criteria: bool
    assisted_api: bool
    runtime_provisioned: bool
    exact_source_head: str

    @property
    def ready(self) -> bool:
        return all((
            self.source_registered,
            self.deterministic_core,
            self.evidence_lineage,
            self.tenant_isolation,
            self.durable_recovery,
            self.adversarial_tests,
            self.delivery_economics_defined,
            self.onboarding_exit_criteria,
            self.assisted_api,
            self.runtime_provisioned,
            bool(_SHA_RE.fullmatch(self.exact_source_head)),
        ))

    def require_ready(self) -> None:
        if self.ready:
            return
        missing = [
            name for name in (
                "source_registered", "deterministic_core", "evidence_lineage", "tenant_isolation",
                "durable_recovery", "adversarial_tests", "delivery_economics_defined",
                "onboarding_exit_criteria", "assisted_api", "runtime_provisioned",
            ) if not getattr(self, name)
        ]
        if not _SHA_RE.fullmatch(self.exact_source_head):
            missing.append("exact_source_head")
        raise PilotReadinessError("pilot readiness incomplete: " + ", ".join(missing))


def assess_recovery_vertical(
    *,
    vertical: str,
    pilot_path: str | Path,
    exact_source_head: str,
    source_registered: bool,
    verified_tests: Iterable[str],
    runtime_provisioned: bool = False,
) -> PilotReadinessEvidence:
    pilot = load_pilot_contract(pilot_path)
    if pilot["vertical"] != vertical:
        raise PilotReadinessError("pilot contract vertical mismatch")
    tests = set(verified_tests)
    return PilotReadinessEvidence(
        vertical=vertical,
        source_registered=source_registered,
        deterministic_core="deterministic_calculation" in tests,
        evidence_lineage="evidence_lineage" in tests,
        tenant_isolation="tenant_isolation" in tests,
        durable_recovery="durable_recovery" in tests,
        adversarial_tests="adversarial" in tests,
        delivery_economics_defined=bool(pilot.get("pricing")),
        onboarding_exit_criteria=bool(pilot.get("pilot_exit_criteria")),
        assisted_api="assisted_api" in tests,
        runtime_provisioned=bool(runtime_provisioned),
        exact_source_head=exact_source_head,
    )
