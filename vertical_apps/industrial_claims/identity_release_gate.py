from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


class IdentityReleaseGateError(ValueError):
    pass


@dataclass(frozen=True)
class MailIdentityEvidence:
    domain: str
    mailbox: str
    domain_owned: bool
    mailbox_verified: bool
    mx_records: tuple[str, ...]
    apex_txt_records: tuple[str, ...]
    dmarc_txt_records: tuple[str, ...]
    dkim_records_by_selector: Mapping[str, Sequence[str]]


@dataclass(frozen=True)
class IdentityReleaseDecision:
    domain: str
    mailbox: str
    mx_present: bool
    spf_valid: bool
    dkim_valid: bool
    dmarc_valid: bool
    dmarc_policy: str | None
    dmarc_enforced: bool
    domain_owned: bool
    mailbox_verified: bool
    ready_for_brand_outbound: bool
    ready_for_public_contact_cta: bool
    blockers: tuple[str, ...]


def _domain(value: object) -> str:
    text = str(value or "").strip().lower().rstrip(".")
    if not text or len(text) > 253 or "." not in text:
        raise IdentityReleaseGateError("canonical domain is invalid")
    labels = text.split(".")
    if any(not label or len(label) > 63 for label in labels):
        raise IdentityReleaseGateError("canonical domain is invalid")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    if any(any(ch not in allowed for ch in label) or label.startswith("-") or label.endswith("-") for label in labels):
        raise IdentityReleaseGateError("canonical domain is invalid")
    return text


def _mailbox(value: object, *, domain: str) -> str:
    text = str(value or "").strip().lower()
    if text.count("@") != 1:
        raise IdentityReleaseGateError("canonical mailbox is invalid")
    local, mailbox_domain = text.split("@", 1)
    if not local or mailbox_domain.rstrip(".") != domain:
        raise IdentityReleaseGateError("canonical mailbox must belong to canonical domain")
    if len(text) > 320 or any(ord(ch) < 33 or ord(ch) == 127 for ch in text):
        raise IdentityReleaseGateError("canonical mailbox is invalid")
    return text


def _records(values: Sequence[object]) -> tuple[str, ...]:
    return tuple(str(value or "").strip() for value in values if str(value or "").strip())


def _spf(records: tuple[str, ...]) -> tuple[bool, str | None]:
    candidates = tuple(record for record in records if record.lower().startswith("v=spf1"))
    if len(candidates) != 1:
        return False, "SPF_MISSING" if not candidates else "SPF_MULTIPLE"
    return True, None


def _dmarc(records: tuple[str, ...]) -> tuple[bool, str | None, str | None, bool]:
    candidates = tuple(record for record in records if record.lower().startswith("v=dmarc1"))
    if len(candidates) != 1:
        return False, "DMARC_MISSING" if not candidates else "DMARC_MULTIPLE", None, False
    tags: dict[str, str] = {}
    for part in candidates[0].split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        value = value.strip().lower()
        if key:
            tags[key] = value
    policy = tags.get("p")
    if policy not in {"none", "quarantine", "reject"}:
        return False, "DMARC_POLICY_INVALID", policy, False
    return True, None, policy, policy in {"quarantine", "reject"}


def _dkim(records_by_selector: Mapping[str, Sequence[str]]) -> tuple[bool, str | None]:
    verified_selectors = 0
    for selector_raw, values in records_by_selector.items():
        selector = str(selector_raw or "").strip().lower()
        if not selector or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in selector):
            continue
        records = _records(tuple(values))
        if any(record.lower().startswith("v=dkim1") for record in records):
            verified_selectors += 1
            continue
        # Many managed-mail providers publish selector._domainkey as CNAME.
        if any("." in record and " " not in record for record in records):
            verified_selectors += 1
    if verified_selectors < 1:
        return False, "DKIM_MISSING"
    return True, None


def evaluate_identity_release(evidence: MailIdentityEvidence) -> IdentityReleaseDecision:
    domain = _domain(evidence.domain)
    mailbox = _mailbox(evidence.mailbox, domain=domain)
    mx_records = _records(evidence.mx_records)
    apex_txt = _records(evidence.apex_txt_records)
    dmarc_txt = _records(evidence.dmarc_txt_records)

    blockers: list[str] = []
    if not evidence.domain_owned:
        blockers.append("DOMAIN_OWNERSHIP_UNVERIFIED")
    if not evidence.mailbox_verified:
        blockers.append("MAILBOX_UNVERIFIED")

    mx_present = bool(mx_records)
    if not mx_present:
        blockers.append("MX_MISSING")

    spf_valid, spf_blocker = _spf(apex_txt)
    if spf_blocker:
        blockers.append(spf_blocker)

    dkim_valid, dkim_blocker = _dkim(evidence.dkim_records_by_selector)
    if dkim_blocker:
        blockers.append(dkim_blocker)

    dmarc_valid, dmarc_blocker, dmarc_policy, dmarc_enforced = _dmarc(dmarc_txt)
    if dmarc_blocker:
        blockers.append(dmarc_blocker)

    ready = not blockers
    return IdentityReleaseDecision(
        domain=domain,
        mailbox=mailbox,
        mx_present=mx_present,
        spf_valid=spf_valid,
        dkim_valid=dkim_valid,
        dmarc_valid=dmarc_valid,
        dmarc_policy=dmarc_policy,
        dmarc_enforced=dmarc_enforced,
        domain_owned=bool(evidence.domain_owned),
        mailbox_verified=bool(evidence.mailbox_verified),
        ready_for_brand_outbound=ready,
        ready_for_public_contact_cta=ready,
        blockers=tuple(blockers),
    )
