from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


class ReleasePreflightError(ValueError):
    pass


_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")


@dataclass(frozen=True)
class ReleaseEvidence:
    canonical_domain: str = "vindorum.com"
    domain_owned: bool = False
    tls_ready: bool = False
    canonical_url: str = ""
    deployment_project: str = ""
    deployment_dedicated: bool = False
    deployment_revision_sha: str = ""
    expected_release_sha: str = ""
    merchant_account_label: str = ""
    merchant_identity_approved_for_vindorum: bool = False
    live_billing_verified: bool = False
    signed_webhook_roundtrip_verified: bool = False
    secure_intake_ready: bool = False
    sender_mailbox: str = ""
    sender_ready: bool = False
    paid_scan_cta_enabled: bool = False


@dataclass(frozen=True)
class ReleaseDecision:
    metadata_site_release_ready: bool
    paid_scan_backend_ready: bool
    commercial_launch_ready: bool
    paid_scan_cta_may_be_enabled: bool
    public_blockers: tuple[str, ...]
    paid_scan_blockers: tuple[str, ...]
    commercial_blockers: tuple[str, ...]
    safety_blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "product": "VINDORUM",
            "metadata_site_release_ready": self.metadata_site_release_ready,
            "paid_scan_backend_ready": self.paid_scan_backend_ready,
            "commercial_launch_ready": self.commercial_launch_ready,
            "paid_scan_cta_may_be_enabled": self.paid_scan_cta_may_be_enabled,
            "public_blockers": list(self.public_blockers),
            "paid_scan_blockers": list(self.paid_scan_blockers),
            "commercial_blockers": list(self.commercial_blockers),
            "safety_blockers": list(self.safety_blockers),
            "truth_boundary": {
                "public_site_live_does_not_mean_paid_scan_live": True,
                "paid_scan_backend_ready_does_not_prove_customer_payment": True,
                "commercial_launch_ready_does_not_prove_buyer_interest": True,
                "production_controls_are_evidence_gates_not_declarations": True,
            },
        }


def _domain(value: object) -> str:
    domain = str(value or "").strip().lower().rstrip(".")
    if not domain or len(domain) > 253 or "." not in domain or not _DOMAIN_RE.fullmatch(domain):
        raise ReleasePreflightError("canonical domain is invalid")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in domain.split(".")):
        raise ReleasePreflightError("canonical domain is invalid")
    return domain


def _canonical_url(value: object, *, domain: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        parsed = urlparse(text)
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    return host in {domain, f"www.{domain}"} and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment


def _sha(value: object) -> str:
    return str(value or "").strip().lower()


def _sender_on_domain(value: object, *, domain: str) -> bool:
    mailbox = str(value or "").strip().lower()
    if mailbox.count("@") != 1:
        return False
    local, mailbox_domain = mailbox.split("@", 1)
    return bool(local) and mailbox_domain.rstrip(".") == domain


def evaluate_release_preflight(evidence: ReleaseEvidence) -> ReleaseDecision:
    if not isinstance(evidence, ReleaseEvidence):
        raise ReleasePreflightError("evidence must be ReleaseEvidence")

    domain = _domain(evidence.canonical_domain)
    expected_sha = _sha(evidence.expected_release_sha)
    deployed_sha = _sha(evidence.deployment_revision_sha)

    public_blockers: list[str] = []
    if not evidence.domain_owned:
        public_blockers.append("DOMAIN_OWNERSHIP_UNVERIFIED")
    if not evidence.tls_ready:
        public_blockers.append("TLS_UNVERIFIED")
    if not _canonical_url(evidence.canonical_url, domain=domain):
        public_blockers.append("CANONICAL_URL_UNVERIFIED")
    if not evidence.deployment_dedicated:
        public_blockers.append("DEDICATED_DEPLOYMENT_UNVERIFIED")
    if "vindorum" not in str(evidence.deployment_project or "").strip().lower():
        public_blockers.append("DEPLOYMENT_IDENTITY_MISMATCH")
    if not _SHA_RE.fullmatch(expected_sha):
        public_blockers.append("EXPECTED_RELEASE_SHA_INVALID")
    if not _SHA_RE.fullmatch(deployed_sha):
        public_blockers.append("DEPLOYED_RELEASE_SHA_INVALID")
    elif _SHA_RE.fullmatch(expected_sha) and deployed_sha != expected_sha:
        public_blockers.append("DEPLOYED_RELEASE_SHA_MISMATCH")

    metadata_site_ready = not public_blockers

    paid_blockers = list(public_blockers)
    if not evidence.merchant_identity_approved_for_vindorum:
        paid_blockers.append("MERCHANT_IDENTITY_NOT_APPROVED_FOR_VINDORUM")
    if not str(evidence.merchant_account_label or "").strip():
        paid_blockers.append("MERCHANT_ACCOUNT_UNIDENTIFIED")
    if not evidence.live_billing_verified:
        paid_blockers.append("LIVE_BILLING_UNVERIFIED")
    if not evidence.signed_webhook_roundtrip_verified:
        paid_blockers.append("SIGNED_WEBHOOK_ROUNDTRIP_UNVERIFIED")
    if not evidence.secure_intake_ready:
        paid_blockers.append("SECURE_INTAKE_NOT_READY")

    paid_backend_ready = not paid_blockers

    commercial_blockers = list(paid_blockers)
    if not evidence.sender_ready:
        commercial_blockers.append("DEDICATED_SENDER_UNVERIFIED")
    if not _sender_on_domain(evidence.sender_mailbox, domain=domain):
        commercial_blockers.append("SENDER_DOMAIN_MISMATCH")

    safety_blockers: list[str] = []
    if evidence.paid_scan_cta_enabled and not paid_backend_ready:
        safety_blockers.append("PAID_SCAN_CTA_PREMATURELY_ENABLED")

    commercial_ready = not commercial_blockers and not safety_blockers
    return ReleaseDecision(
        metadata_site_release_ready=metadata_site_ready,
        paid_scan_backend_ready=paid_backend_ready,
        commercial_launch_ready=commercial_ready,
        paid_scan_cta_may_be_enabled=paid_backend_ready,
        public_blockers=tuple(dict.fromkeys(public_blockers)),
        paid_scan_blockers=tuple(dict.fromkeys(paid_blockers)),
        commercial_blockers=tuple(dict.fromkeys(commercial_blockers)),
        safety_blockers=tuple(safety_blockers),
    )
