from __future__ import annotations

from dataclasses import dataclass
from email.utils import parseaddr
from hashlib import sha256


# Fingerprints intentionally avoid embedding identities/domains belonging to other products
# inside the VINDORUM runtime while still failing closed when one is supplied.
FORBIDDEN_SENDER_DOMAIN_SHA256 = {
    "fc8c1bdca8f87e53b14580d069417680d240565bd7e47ad5ae2eba0cb900bafd",
    "2666dd4ae482699793c64b9e999d5dab09ad7b5b11345a0f153fd2cee06cc4ff",
    "4a00de4b1c952d229f33ca7077b847bb6478366c3a306e7728b6cf1c2e5e1983",
}


def _domain_fingerprint(domain: str) -> str:
    return sha256(domain.strip().lower().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SenderIdentity:
    product: str
    from_address: str
    dedicated_to_product: bool
    reply_capable: bool
    outbound_auth_verified: bool
    suppression_ready: bool

    @property
    def domain(self) -> str:
        address = parseaddr(self.from_address)[1]
        return address.rsplit("@", 1)[1].lower() if "@" in address else ""


@dataclass(frozen=True)
class PreflightChecks:
    founder_authorized: bool = False
    role_recheck_passed: bool = False
    route_recheck_passed: bool = False
    confidential_documents_requested: bool = False


@dataclass(frozen=True)
class PreflightDecision:
    ready_to_send: bool
    next_state: str
    blockers: tuple[str, ...]


def evaluate_outbound_preflight(*, record: dict, route: dict, sender: SenderIdentity | None, checks: PreflightChecks) -> PreflightDecision:
    """Fail-closed VINDORUM outbound decision. This function never sends email."""
    blockers: list[str] = []
    if record.get("status") not in {"PREPARED_NOT_SENDABLE", "READY_FOR_FOUNDER_AUTHORIZATION", "AUTHORIZED_NOT_SENT"}:
        blockers.append("record_not_in_pre_send_state")
    if record.get("account_id") != route.get("account_id"):
        blockers.append("route_account_mismatch")
    if route.get("outbound_authorized") is not False:
        blockers.append("route_truth_boundary_changed")
    if checks.confidential_documents_requested:
        blockers.append("confidential_documents_not_allowed_in_first_contact")
    if record.get("role_recheck_required") and not checks.role_recheck_passed:
        blockers.append("role_recheck_required")
    if record.get("route_recheck_required") and not checks.route_recheck_passed:
        blockers.append("route_recheck_required")

    if sender is None:
        blockers.append("dedicated_sender_missing")
    else:
        if sender.product != "VINDORUM":
            blockers.append("sender_product_mismatch")
        if not sender.dedicated_to_product:
            blockers.append("sender_not_dedicated")
        if not sender.reply_capable:
            blockers.append("sender_cannot_receive_replies")
        if not sender.outbound_auth_verified:
            blockers.append("sender_auth_not_verified")
        if not sender.suppression_ready:
            blockers.append("suppression_not_ready")
        if not sender.domain:
            blockers.append("sender_domain_invalid")
        elif _domain_fingerprint(sender.domain) in FORBIDDEN_SENDER_DOMAIN_SHA256:
            blockers.append("cross_project_or_generic_sender_forbidden")

    if blockers:
        return PreflightDecision(False, "PREPARED_NOT_SENDABLE", tuple(blockers))
    if not checks.founder_authorized:
        return PreflightDecision(False, "READY_FOR_FOUNDER_AUTHORIZATION", ("founder_send_authorization_required",))
    return PreflightDecision(True, "AUTHORIZED_NOT_SENT", ())
