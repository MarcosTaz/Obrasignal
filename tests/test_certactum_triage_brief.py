import pytest

from vertical_apps.industrial_claims.metadata_triage import MetadataTriageInput, evaluate_metadata_triage
from vertical_apps.industrial_claims.triage_brief import (
    MetadataTriageBriefError,
    MetadataTriageCase,
    render_metadata_triage_brief,
)


def _case():
    return MetadataTriageCase(
        industry="Automotive Tier 2",
        customer_type="OEM / Tier 1 customer",
        change_type="Customer-directed engineering change / NRE",
        exposure_band="EUR 50k–150k approximate, unverified",
        economic_owner_role="Commercial Director",
        desired_outcome="Determine whether a bounded forensic recovery audit is justified.",
    )


def test_metadata_qualified_brief_is_sellable_without_claiming_recovery():
    result = evaluate_metadata_triage(
        MetadataTriageInput(
            mechanism_in_scope=True,
            customer_change_identifiable=True,
            incremental_cost_source_exists=True,
            commercial_basis_document_exists=True,
            prior_recovery_reconstructable=True,
            notice_process_known=True,
            economic_owner_named=True,
            exposure_exceeds_likely_audit_fee=True,
        )
    )
    brief = render_metadata_triage_brief(case=_case(), result=result)

    assert brief.startswith("# Certactum — Metadata Recovery Triage")
    assert "Qualification: **METADATA_QUALIFIED**" in brief
    assert "Fit-routing score: 10/10" in brief
    assert "Recoverability scored: False" in brief
    assert "does not establish recoverability" in brief
    assert "Documentary work remains gated" in brief
    assert "Do not attach or email confidential contracts" in brief


def test_prequalification_brief_surfaces_unknown_questions_not_invented_evidence():
    result = evaluate_metadata_triage(
        MetadataTriageInput(
            mechanism_in_scope=True,
            customer_change_identifiable=True,
            incremental_cost_source_exists=True,
            commercial_basis_document_exists=None,
            prior_recovery_reconstructable=None,
            notice_process_known=None,
            economic_owner_named=False,
            exposure_exceeds_likely_audit_fee=False,
        )
    )
    brief = render_metadata_triage_brief(case=_case(), result=result)

    assert "Qualification: **NEEDS_PREQUALIFICATION**" in brief
    assert "commercial_basis_document_exists" in brief
    assert "prior_recovery_reconstructable" in brief
    assert "notice_process_known" in brief
    assert "Resolve the open metadata questions" in brief


def test_out_of_scope_brief_preserves_factory_boundary():
    result = evaluate_metadata_triage(MetadataTriageInput(mechanism_in_scope=False))
    brief = render_metadata_triage_brief(case=_case(), result=result)
    assert "Qualification: **NO_FIT**" in brief
    assert "Do not widen Supplier Recovery to force fit" in brief


def test_triage_brief_rejects_control_characters():
    case = _case()
    object.__setattr__(case, "industry", "Automotive\x00")
    result = evaluate_metadata_triage(MetadataTriageInput(mechanism_in_scope=False))
    with pytest.raises(MetadataTriageBriefError, match="control characters"):
        render_metadata_triage_brief(case=case, result=result)
