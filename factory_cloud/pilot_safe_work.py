from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PilotSafeWorkItem:
    factory_id: str
    evidence_key: str
    task: str
    priority: int
    scope: str


WORK_CATALOG = {
    "source_registered": (1000, "vertical", "register_and_verify_canonical_source_truth"),
    "exact_source_head": (990, "vertical", "prove_exact_source_head"),
    "tenant_isolation": (970, "shared", "prove_tenant_and_role_isolation"),
    "adversarial": (960, "shared", "run_adversarial_failure_suite"),
    "end_to_end_product": (940, "vertical", "complete_and_prove_end_to_end_product"),
    "web_complete": (930, "shared", "complete_and_prove_web_interface_states"),
    "durable_recovery": (910, "shared", "prove_durable_recovery"),
    "backup_restore": (900, "shared", "prove_backup_restore"),
    "observability": (890, "shared", "prove_observability_and_alerting"),
    "support_continuity": (880, "shared", "prove_support_and_incident_continuity"),
    "deterministic_calculation": (860, "shared", "prove_deterministic_calculation"),
    "evidence_lineage": (850, "shared", "prove_evidence_lineage"),
    "assisted_api": (830, "shared", "complete_and_prove_assisted_api"),
    "billing_sandbox": (810, "shared", "run_billing_sandbox_end_to_end"),
    "synthetic_company_e2e": (800, "vertical", "run_synthetic_company_end_to_end"),
    "shadow_validation": (780, "vertical", "run_real_world_shadow_validation"),
    "wedge_defined": (760, "vertical", "freeze_wedge"),
    "buyer_defined": (750, "vertical", "freeze_buyer_and_user_roles"),
    "economic_or_entitlement_basis_defined": (740, "vertical", "freeze_economic_or_entitlement_basis"),
    "non_claims_defined": (730, "vertical", "freeze_non_claims_and_fail_closed_boundaries"),
    "delivery_economics_defined": (710, "vertical", "define_delivery_economics"),
    "onboarding_exit_criteria": (700, "vertical", "define_onboarding_and_exit_criteria"),
}


def work_for_missing(factory_id: str, missing_evidence: Iterable[str]) -> list[PilotSafeWorkItem]:
    items = []
    for key in set(missing_evidence):
        priority, scope, task = WORK_CATALOG.get(key, (500, "vertical", f"prove_{key}"))
        items.append(PilotSafeWorkItem(factory_id, key, task, priority, scope))
    return sorted(items, key=lambda item: (-item.priority, item.evidence_key))


def next_work(factory_id: str, missing_evidence: Iterable[str]) -> PilotSafeWorkItem | None:
    items = work_for_missing(factory_id, missing_evidence)
    return items[0] if items else None


def portfolio_work_queue(matrix: Iterable[dict]) -> list[PilotSafeWorkItem]:
    items = []
    for row in matrix:
        if row.get("classification") == "PILOT_SAFE":
            continue
        items.extend(work_for_missing(str(row["factory_id"]), row.get("missing_evidence", ())))
    return sorted(items, key=lambda item: (-item.priority, item.scope != "shared", item.factory_id, item.evidence_key))
