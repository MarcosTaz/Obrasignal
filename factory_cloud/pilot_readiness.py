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
    end_to_end_product: bool
    web_complete: bool
    backup_restore: bool
    observability: bool
    support_continuity: bool
    billing_sandbox: bool
    synthetic_company_e2e: bool
    shadow_validation: bool
    exact_source_head: str

    @property
    def ready(self) -> bool:
        """PILOT_SAFE only: no real customer/data/payment authority is granted here."""
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
            self.end_to_end_product,
            self.web_complete,
            self.backup_restore,
            self.observability,
            self.support_continuity,
            self.billing_sandbox,
            self.synthetic_company_e2e,
            self.shadow_validation,
            bool(_SHA_RE.fullmatch(self.exact_source_head)),
        ))

    @property
    def classification(self) -> str:
        return "PILOT_SAFE" if self.ready else "NOT_PILOT_SAFE"

    def missing_proofs(self) -> list[str]:
        missing = [
            name for name in (
                "source_registered",
                "deterministic_core",
                "evidence_lineage",
                "tenant_isolation",
                "durable_recovery",
                "adversarial_tests",
                "delivery_economics_defined",
                "onboarding_exit_criteria",
                "assisted_api",
                "end_to_end_product",
                "web_complete",
                "backup_restore",
                "observability",
                "support_continuity",
                "billing_sandbox",
                "synthetic_company_e2e",
                "shadow_validation",
            ) if not getattr(self, name)
        ]
        if not _SHA_RE.fullmatch(self.exact_source_head):
            missing.append("exact_source_head")
        return missing

    def require_ready(self) -> None:
        if self.ready:
            return
        raise PilotReadinessError("pilot-safe readiness incomplete: " + ", ".join(self.missing_proofs()))


def assess_recovery_vertical(*, vertical: str, pilot_path: str | Path, exact_source_head: str, source_registered: bool, verified_tests: Iterable[str]) -> PilotReadinessEvidence:
    """Assess pre-customer PILOT_SAFE evidence.

    Synthetic/shadow proof is deliberately required before any Factory can be
    classified ready for a controlled real pilot. This function does not grant
    production, customer-data, billing, deploy or market-validation authority.
    """
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
        end_to_end_product="end_to_end_product" in tests,
        web_complete="web_complete" in tests,
        backup_restore="backup_restore" in tests,
        observability="observability" in tests,
        support_continuity="support_continuity" in tests,
        billing_sandbox="billing_sandbox" in tests,
        synthetic_company_e2e="synthetic_company_e2e" in tests,
        shadow_validation="shadow_validation" in tests,
        exact_source_head=exact_source_head,
    )
