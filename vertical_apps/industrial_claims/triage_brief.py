from __future__ import annotations

from dataclasses import dataclass

from vertical_apps.industrial_claims.metadata_triage import MetadataTriageResult


class MetadataTriageBriefError(ValueError):
    pass


MAX_FIELD_CHARS = 500


def _bounded(value: object, *, label: str, required: bool = True) -> str:
    raw = str(value or "")
    if any((ord(char) < 32 and char not in "\t\n\r") or ord(char) == 127 for char in raw):
        raise MetadataTriageBriefError(f"{label} contains forbidden control characters")
    text = raw.strip()
    if required and not text:
        raise MetadataTriageBriefError(f"{label} is required")
    if len(text) > MAX_FIELD_CHARS:
        raise MetadataTriageBriefError(f"{label} exceeds {MAX_FIELD_CHARS} characters")
    return text


@dataclass(frozen=True)
class MetadataTriageCase:
    industry: str
    customer_type: str
    change_type: str
    exposure_band: str
    economic_owner_role: str
    desired_outcome: str


def render_metadata_triage_brief(*, case: MetadataTriageCase, result: MetadataTriageResult) -> str:
    """Render a bounded pre-document VINDORUM qualification brief."""
    if not isinstance(case, MetadataTriageCase):
        raise MetadataTriageBriefError("case must be MetadataTriageCase")
    if not isinstance(result, MetadataTriageResult):
        raise MetadataTriageBriefError("result must be MetadataTriageResult")
    if result.recoverability_scored or result.confidential_document_intake_required:
        raise MetadataTriageBriefError("metadata triage result violates pre-document boundary")

    industry = _bounded(case.industry, label="industry")
    customer_type = _bounded(case.customer_type, label="customer_type")
    change_type = _bounded(case.change_type, label="change_type")
    exposure_band = _bounded(case.exposure_band, label="exposure_band")
    owner = _bounded(case.economic_owner_role, label="economic_owner_role")
    outcome = _bounded(case.desired_outcome, label="desired_outcome")

    positives = [f"- {item}" for item in result.observed_positive_signals] or ["- None confirmed yet."]
    unknowns = [f"- {item}" for item in result.unknown_signals] or ["- None recorded."]
    questions = [f"- {item}" for item in result.next_questions] or ["- No additional metadata question required before routing."]

    if result.qualification == "METADATA_QUALIFIED":
        route = "Create the case workspace. Documentary work remains gated behind verified secure intake."
    elif result.qualification == "NEEDS_PREQUALIFICATION":
        route = "Resolve the open metadata questions in the self-service flow before documentary analysis."
    elif result.qualification == "WEAK_FIT":
        route = "Do not request documents yet. Confirm mechanism, evidence existence and economic ownership first."
    elif result.qualification == "NO_FIT":
        route = "Do not widen VINDORUM to force fit. Close this path without purchasing a scan."
    else:
        raise MetadataTriageBriefError("unsupported metadata qualification")

    return "\n".join([
        "# VINDORUM — Metadata Recovery Triage", "",
        "> Pre-document qualification only. This brief does not establish recoverability, legal entitlement or money owed.", "",
        "## Case metadata", f"- Industry: {industry}", f"- Customer/OEM type: {customer_type}",
        f"- Change/event type: {change_type}", f"- Approximate exposure band: {exposure_band}",
        f"- Economic owner role: {owner}", f"- Desired review outcome: {outcome}", "",
        "## Routing result", f"- Qualification: **{result.qualification}**", f"- Fit-routing score: {result.score}/10",
        "- Recoverability scored: False", "- Confidential document intake required for this triage: False", "",
        "## Confirmed positive signals", *positives, "", "## Unknown metadata", *unknowns, "",
        "## Next questions", *questions, "", "## Self-service route", route, "", "## Data boundary",
        "Do not attach or email confidential contracts, POs, drawings, ECNs, invoices or ledgers at this stage.", "",
    ])
