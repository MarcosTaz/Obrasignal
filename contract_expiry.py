"""Conservative contract-expiry intelligence for canonical CONTRACT signals.

Expiry is temporal evidence, not evidence that a replacement procurement exists.
The evaluator is pure: callers inject both the clock and policy.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from typing import Mapping

POLICY_VERSION = "contract-expiry.v0"


@dataclass(frozen=True)
class ExpiryPolicy:
    near_term_days: int = 90
    mid_near_days: int = 180
    forward_days: int = 365
    max_future_days: int = 730
    expired_lookback_days: int = 90
    eligible_statuses: tuple[str, ...] = ("ACTIVE", "UNKNOWN")
    version: str = POLICY_VERSION

    def __post_init__(self):
        bounds = (self.near_term_days, self.mid_near_days, self.forward_days, self.max_future_days)
        if any(v < 0 for v in bounds) or tuple(sorted(bounds)) != bounds:
            raise ValueError("expiry horizons must be non-negative and ordered")
        if self.expired_lookback_days < 0:
            raise ValueError("expired_lookback_days must be non-negative")


@dataclass(frozen=True)
class EndDateEvidence:
    value: date | None
    precision: str
    basis: str
    source_reference: str | None = None
    calculation: str | None = None


@dataclass(frozen=True)
class ExpiryAssessment:
    signal_id: str
    contract_id: str
    status: str
    expiry_window: str
    current_known_end: str | None
    end_date_precision: str
    end_date_basis: str
    days_to_expiry: int | None
    reason_codes: tuple[str, ...]
    buyer_id: str | None = None
    incumbent_id: str | None = None
    category: str | None = None
    location: str | None = None
    contract_start: str | None = None
    prior_known_contract_value: object | None = None
    currency: str | None = None
    renewal_options_known: bool = False
    extension_status: str = "NONE_KNOWN"
    source_ref: str | None = None
    freshness_ref: str | None = None
    lineage_ref: str | None = None
    policy_version: str = POLICY_VERSION
    generated_at: str | None = field(default=None, compare=False)
    signal_type: str = "CONTRACT_EXPIRY"
    is_open_tender: bool = False
    replacement_procurement_confirmed: bool = False
    warning: str = "No replacement procurement has been confirmed."

    def as_signal_record(self) -> dict:
        """Serialize without ever masquerading as an actionable TENDER."""
        return {
            "source": "CONTRACT_EXPIRY_ENGINE",
            "signal_type": self.signal_type,
            "external_id": self.signal_id,
            "title": "Known contract approaches end of term" if self.status == "EXPIRING" else "Known contract term status",
            "target_date": self.current_known_end,
            "source_reference": self.source_ref or self.contract_id,
            "contract_id": self.contract_id,
            "buyer_id": self.buyer_id,
            "incumbent_id": self.incumbent_id,
            "category": self.category,
            "place": self.location,
            "contract_start": self.contract_start,
            "current_known_end": self.current_known_end,
            "end_date_precision": self.end_date_precision,
            "end_date_basis": self.end_date_basis,
            "days_to_expiry": self.days_to_expiry,
            "expiry_window": self.expiry_window,
            "contract_status": self.status,
            "prior_known_contract_value": self.prior_known_contract_value,
            "currency": self.currency,
            "renewal_options_known": self.renewal_options_known,
            "extension_status": self.extension_status,
            "freshness_ref": self.freshness_ref,
            "lineage_ref": self.lineage_ref,
            "reason_codes": list(self.reason_codes),
            "policy_version": self.policy_version,
            "generated_at": self.generated_at,
            "is_open_tender": False,
            "replacement_procurement_confirmed": False,
            "warning": self.warning,
        }


def _text(value):
    return str(value).strip() if value not in (None, "") else None


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except (ValueError, TypeError):
        return None


def _clock_date(now) -> date:
    parsed = _as_date(now)
    if parsed is None:
        raise ValueError("now must be a valid date/datetime")
    return parsed


def add_calendar_months(start: date, months: int) -> date:
    """Calendar-month arithmetic with end-of-month clamping (Jan 31 + 1 => Feb end)."""
    if not isinstance(months, int) or isinstance(months, bool) or months < 0 or months > 1200:
        raise ValueError("duration months must be an integer between 0 and 1200")
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    if year > 9999:
        raise ValueError("derived contract end exceeds supported date range")
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_duration(start: date, amount, unit: str) -> date:
    if isinstance(amount, bool):
        raise ValueError("duration amount must be an integer")
    try:
        amount = int(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("duration amount must be an integer") from exc
    if amount < 0:
        raise ValueError("duration amount must be non-negative")
    unit = str(unit or "").strip().lower()
    if unit in {"day", "days"}:
        if amount > 365000:
            raise ValueError("duration days exceeds safety limit")
        return start + timedelta(days=amount)
    if unit in {"month", "months"}:
        return add_calendar_months(start, amount)
    if unit in {"year", "years"}:
        if amount > 100:
            raise ValueError("duration years exceeds safety limit")
        return add_calendar_months(start, amount * 12)
    raise ValueError("unsupported duration unit")


def _partial_date(record: Mapping) -> EndDateEvidence | None:
    year = record.get("contract_end_year")
    month = record.get("contract_end_month")
    quarter = record.get("contract_end_quarter")
    if year in (None, ""):
        return None
    try:
        year = int(year)
    except (TypeError, ValueError):
        return None
    if not 1900 <= year <= 9999:
        return None
    if month not in (None, ""):
        try:
            month = int(month)
            if 1 <= month <= 12:
                return EndDateEvidence(None, "MONTH", "PARTIAL", calculation=f"{year:04d}-{month:02d}")
        except (TypeError, ValueError):
            pass
    if quarter not in (None, ""):
        try:
            quarter = int(quarter)
            if 1 <= quarter <= 4:
                return EndDateEvidence(None, "QUARTER", "PARTIAL", calculation=f"{year:04d}-Q{quarter}")
        except (TypeError, ValueError):
            pass
    return EndDateEvidence(None, "YEAR", "PARTIAL", calculation=f"{year:04d}")


def resolve_current_end(record: Mapping) -> EndDateEvidence:
    """Resolve current known term conservatively; an option alone never extends it."""
    source_ref = _text(record.get("source_reference"))
    extension = _as_date(record.get("extended_to"))
    extension_confirmed = bool(record.get("extension_confirmed"))
    official = _as_date(record.get("contract_end_date") or record.get("current_term_end"))
    if extension_confirmed and extension:
        if official and extension < official:
            # Later revisions may correct an end date, but a field explicitly named
            # extension must not silently shorten the known term.
            extension = official
        return EndDateEvidence(extension, "DAY", "OFFICIAL_EXTENSION", source_ref)
    if official:
        return EndDateEvidence(official, "DAY", "OFFICIAL", source_ref)

    partial = _partial_date(record)
    if partial:
        return EndDateEvidence(None, partial.precision, partial.basis, source_ref, partial.calculation)

    start = _as_date(record.get("contract_start_date"))
    amount = record.get("duration_amount")
    unit = _text(record.get("duration_unit"))
    if start and amount not in (None, "") and unit:
        try:
            end = add_duration(start, amount, unit)
        except ValueError:
            return EndDateEvidence(None, "UNKNOWN", "UNKNOWN", source_ref)
        return EndDateEvidence(end, "DAY", "DERIVED", source_ref, f"{start.isoformat()} + {int(amount)} {unit}")
    return EndDateEvidence(None, "UNKNOWN", "UNKNOWN", source_ref)


def _signal_id(contract_id: str, evidence: EndDateEvidence, policy: ExpiryPolicy) -> str:
    version = evidence.value.isoformat() if evidence.value else (evidence.calculation or "unknown")
    digest = sha256(f"{contract_id}|{version}|{evidence.basis}|{policy.version}".encode()).hexdigest()[:24]
    return f"contract-expiry:{digest}"


def _window(days: int, policy: ExpiryPolicy) -> str:
    if days < 0:
        return "EXPIRED"
    if days <= policy.near_term_days:
        return "NEAR_TERM"
    if days <= policy.mid_near_days:
        return "MID_NEAR"
    if days <= policy.forward_days:
        return "FORWARD"
    return "LONG_HORIZON"


def evaluate_contract_expiry(contract: Mapping, now, policy: ExpiryPolicy | None = None) -> ExpiryAssessment:
    if not isinstance(contract, Mapping):
        raise ValueError("contract must be a mapping")
    policy = policy or ExpiryPolicy()
    today = _clock_date(now)
    signal_type = str(contract.get("signal_type") or "").strip().upper()
    contract_id = _text(contract.get("contract_id") or (contract.get("external_id") if signal_type == "CONTRACT" else None))
    if not contract_id:
        raise ValueError("canonical contract_id is required; an award is not a contract")

    raw_status = str(contract.get("contract_status") or "UNKNOWN").strip().upper()
    evidence = resolve_current_end(contract)
    reasons = []
    renewal_options = bool(contract.get("renewal_options") or contract.get("option_periods") or contract.get("max_possible_end"))
    extension_status = "CONFIRMED" if bool(contract.get("extension_confirmed")) and _as_date(contract.get("extended_to")) else ("OPTION_EXISTS_NOT_EXERCISED" if renewal_options else "NONE_KNOWN")

    status = "UNKNOWN"
    expiry_window = "UNKNOWN"
    days = None
    if raw_status in {"TERMINATED", "CANCELLED"}:
        status = raw_status
        reasons.append("CONTRACT_TERMINATED" if raw_status == "TERMINATED" else "CONTRACT_CANCELLED")
    elif raw_status == "COMPLETED":
        status = "COMPLETED"
        reasons.append("CONTRACT_COMPLETED")
    elif evidence.value is None:
        reasons.append("INSUFFICIENT_DATE_DATA")
    else:
        days = (evidence.value - today).days
        expiry_window = _window(days, policy)
        if days < 0:
            status = "EXPIRED"
            reasons.append("CONTRACT_ALREADY_EXPIRED")
        elif raw_status not in policy.eligible_statuses and raw_status != "EXTENDED":
            status = raw_status
        elif days > policy.max_future_days:
            status = "OUTSIDE_HORIZON"
        else:
            status = "EXPIRING"
            reasons.append("DERIVED_TERM_END_APPROACHING" if evidence.basis == "DERIVED" else "OFFICIAL_END_DATE_APPROACHING")
    if extension_status == "CONFIRMED":
        reasons.append("EXTENSION_CONFIRMED")
    elif extension_status == "OPTION_EXISTS_NOT_EXERCISED":
        reasons.append("OPTION_EXISTS_NOT_EXERCISED")

    current_end = evidence.value.isoformat() if evidence.value else evidence.calculation
    generated = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    return ExpiryAssessment(
        signal_id=_signal_id(contract_id, evidence, policy),
        contract_id=contract_id,
        status=status,
        expiry_window=expiry_window,
        current_known_end=current_end,
        end_date_precision=evidence.precision,
        end_date_basis=evidence.basis,
        days_to_expiry=days,
        reason_codes=tuple(reasons),
        buyer_id=_text(contract.get("buyer_id") or contract.get("buyer")),
        incumbent_id=_text(contract.get("incumbent_id") or contract.get("supplier_id")),
        category=_text(contract.get("category") or contract.get("contract_type")),
        location=_text(contract.get("location") or contract.get("place")),
        contract_start=_text(contract.get("contract_start_date")),
        prior_known_contract_value=contract.get("current_contract_value", contract.get("contract_value")),
        currency=_text(contract.get("currency")),
        renewal_options_known=renewal_options,
        extension_status=extension_status,
        source_ref=evidence.source_reference,
        freshness_ref=_text(contract.get("freshness_ref")),
        lineage_ref=_text(contract.get("lineage_ref")),
        policy_version=policy.version,
        generated_at=generated,
    )


def actionable_expiry_signal(assessment: ExpiryAssessment, policy: ExpiryPolicy | None = None) -> bool:
    """Feed eligibility; recently expired rows may remain contextual, never open tenders."""
    policy = policy or ExpiryPolicy()
    if assessment.status == "EXPIRING":
        return True
    return assessment.status == "EXPIRED" and assessment.days_to_expiry is not None and abs(assessment.days_to_expiry) <= policy.expired_lookback_days
