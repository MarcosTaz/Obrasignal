from __future__ import annotations

from dataclasses import dataclass


class MetadataTriageError(ValueError):
    pass


@dataclass(frozen=True)
class MetadataTriageInput:
    mechanism_in_scope: bool
    customer_change_identifiable: bool | None = None
    incremental_cost_source_exists: bool | None = None
    commercial_basis_document_exists: bool | None = None
    prior_recovery_reconstructable: bool | None = None
    notice_process_known: bool | None = None
    economic_owner_named: bool | None = None
    exposure_exceeds_likely_audit_fee: bool | None = None


@dataclass(frozen=True)
class MetadataTriageResult:
    score: int
    qualification: str
    observed_positive_signals: tuple[str, ...]
    unknown_signals: tuple[str, ...]
    next_questions: tuple[str, ...]
    recoverability_scored: bool = False
    confidential_document_intake_required: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "qualification": self.qualification,
            "observed_positive_signals": list(self.observed_positive_signals),
            "unknown_signals": list(self.unknown_signals),
            "next_questions": list(self.next_questions),
            "recoverability_scored": self.recoverability_scored,
            "confidential_document_intake_required": self.confidential_document_intake_required,
        }


_FIELDS = (
    ("customer_change_identifiable", 2, "Can a specific customer/OEM change or event be identified?"),
    ("incremental_cost_source_exists", 2, "Does a source for incremental engineering/NRE cost exist?"),
    ("commercial_basis_document_exists", 2, "Does a PO/contract/change document exist for commercial review?"),
    ("prior_recovery_reconstructable", 1, "Can prior claim/approval/payment state be reconstructed?"),
    ("notice_process_known", 1, "Is the notice/deadline process known or checkable?"),
    ("economic_owner_named", 1, "Is there a named internal economic owner for recovery?"),
    ("exposure_exceeds_likely_audit_fee", 1, "Is the approximate exposure comfortably above the likely scan fee?"),
)


def _validate_optional_bool(value: bool | None, *, label: str) -> None:
    if value is not None and not isinstance(value, bool):
        raise MetadataTriageError(f"{label} must be true, false or unknown")


def evaluate_metadata_triage(payload: MetadataTriageInput) -> MetadataTriageResult:
    if not isinstance(payload, MetadataTriageInput):
        raise MetadataTriageError("payload must be MetadataTriageInput")
    if not isinstance(payload.mechanism_in_scope, bool):
        raise MetadataTriageError("mechanism_in_scope must be boolean")

    for field, _weight, _question in _FIELDS:
        _validate_optional_bool(getattr(payload, field), label=field)

    if not payload.mechanism_in_scope:
        return MetadataTriageResult(
            score=0,
            qualification="NO_FIT",
            observed_positive_signals=(),
            unknown_signals=(),
            next_questions=("This mechanism is outside VINDORUM's current industrial change-cost scope.",),
        )

    score = 0
    positives: list[str] = []
    unknowns: list[str] = []
    questions: list[str] = []
    for field, weight, question in _FIELDS:
        value = getattr(payload, field)
        if value is True:
            score += weight
            positives.append(field)
        elif value is None:
            unknowns.append(field)
            questions.append(question)

    if score <= 3:
        qualification = "WEAK_FIT"
    elif score <= 6:
        qualification = "NEEDS_PREQUALIFICATION"
    else:
        qualification = "METADATA_QUALIFIED"

    return MetadataTriageResult(
        score=score,
        qualification=qualification,
        observed_positive_signals=tuple(positives),
        unknown_signals=tuple(unknowns),
        next_questions=tuple(questions),
    )
