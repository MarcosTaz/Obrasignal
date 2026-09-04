from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from vertical_apps.industrial_claims.dossier import (
    AssistedRecoveryAssessment,
    build_assisted_dossier,
    render_dossier_markdown,
)
from vertical_apps.industrial_claims.leakage_reconciliation import RecoveryLedgerSnapshot
from vertical_apps.industrial_claims.service import IndustrialClaimsService


CERTACTUM_DOSSIER = "CERTACTUM_SUPPLIER_RECOVERY_DOSSIER"
LEGACY_DOSSIER = "CAUSLEDGER_ASSISTED_RECOVERY_DOSSIER"


def build_certactum_recovery_dossier(
    service: IndustrialClaimsService,
    *,
    tenant_id: str,
    finding_id: str,
    assessment: AssistedRecoveryAssessment,
    reconciliation: RecoveryLedgerSnapshot,
    as_of_date: date | None = None,
) -> dict[str, Any]:
    """Build the canonical Certactum supplier-recovery dossier.

    The underlying legacy dossier schema remains readable for lineage compatibility,
    while every new customer-facing dossier uses the Certactum identity and carries
    an explicit recovery-ledger reconciliation. The reconciliation is supplied from
    the fail-closed ledger engine and does not establish legal entitlement.
    """
    base = build_assisted_dossier(
        service,
        tenant_id=tenant_id,
        finding_id=finding_id,
        assessment=assessment,
        as_of_date=as_of_date,
    )
    dossier = deepcopy(base)
    dossier["schema_version"] = 2
    dossier["deliverable"] = CERTACTUM_DOSSIER
    dossier["recovery_reconciliation"] = {
        **reconciliation.as_dict(),
        "legal_entitlement_established": False,
        "economic_gap_is_automatically_money_owed": False,
    }
    dossier["identity"] = {
        "company": "Certactum",
        "legacy_schema_source": LEGACY_DOSSIER,
        "legacy_name_customer_facing": False,
    }
    return dossier


def render_certactum_recovery_dossier_markdown(dossier: dict[str, Any]) -> str:
    if dossier.get("deliverable") != CERTACTUM_DOSSIER:
        raise ValueError("unsupported Certactum dossier deliverable")
    reconciliation = dossier.get("recovery_reconciliation")
    if not isinstance(reconciliation, dict):
        raise ValueError("Certactum dossier requires recovery reconciliation")
    if reconciliation.get("legal_entitlement_established") is not False:
        raise ValueError("reconciliation cannot assert legal entitlement")
    if reconciliation.get("economic_gap_is_automatically_money_owed") is not False:
        raise ValueError("reconciliation cannot promote an economic gap to money owed")

    legacy = deepcopy(dossier)
    legacy["deliverable"] = LEGACY_DOSSIER
    legacy.pop("recovery_reconciliation", None)
    legacy.pop("identity", None)
    markdown = render_dossier_markdown(legacy)
    markdown = markdown.replace("# CausLedger — Assisted Recovery Dossier", "# Certactum — Supplier Recovery Dossier", 1)

    signals = reconciliation.get("signals") or []
    signal_lines = [f"- {str(signal)}" for signal in signals] or ["- No recovery-ledger signal."]
    section = [
        "## Recovery reconciliation",
        f"- Net documented exposure: {reconciliation.get('net_documented_exposure')} {reconciliation.get('currency')}",
        f"- Evidence-supported: {reconciliation.get('evidence_supported')} {reconciliation.get('currency')}",
        f"- Claimed: {reconciliation.get('claimed')} {reconciliation.get('currency')}",
        f"- Approved: {reconciliation.get('approved')} {reconciliation.get('currency')}",
        f"- Settled: {reconciliation.get('settled')} {reconciliation.get('currency')}",
        f"- Unsupported exposure: {reconciliation.get('unsupported_exposure')} {reconciliation.get('currency')}",
        f"- Supported but unclaimed: {reconciliation.get('supported_unclaimed')} {reconciliation.get('currency')}",
        f"- Claimed but unapproved: {reconciliation.get('claimed_unapproved')} {reconciliation.get('currency')}",
        f"- Approved but unsettled: {reconciliation.get('approved_unsettled')} {reconciliation.get('currency')}",
        f"- Evidence-supported still unsettled: {reconciliation.get('supported_unsettled')} {reconciliation.get('currency')}",
        f"- Reconciliation hash: `{reconciliation.get('reconciliation_hash')}`",
        "- Economic gap automatically establishes money owed: False",
        "- Legal entitlement established by reconciliation: False",
        "",
        "### Reconciliation signals",
        *signal_lines,
        "",
    ]

    marker = "## Next action"
    if marker in markdown:
        markdown = markdown.replace(marker, "\n".join(section) + marker, 1)
    else:
        markdown = markdown.rstrip() + "\n\n" + "\n".join(section)
    return markdown
