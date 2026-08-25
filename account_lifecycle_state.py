"""Executable, observational customer-account lifecycle projection.

This module does not own Auth, Billing, Evaluation, Mobile, Notification, or
Persistence implementation. It maps repository-proven account fields into a
privacy/lifecycle view without inventing product states or transition authority.
"""
from __future__ import annotations


DELETION_ACCOUNT_STATUSES = {
    "deletion_pending",
    "deletion_failed",
    "deleted_pending_revocation",
    "deleted",
}


def project_account_lifecycle(account: dict | None) -> dict:
    """Return a fail-closed lifecycle projection from one persisted account row.

    `account.status` is kept separate from Billing/Evaluation axes because current
    repository storage does not encode EVALUATION/PRO/CANCELLED as account.status
    states. Unknown values remain UNKNOWN instead of being coerced.
    """
    if not account:
        return {
            "account_state": "NOT_FOUND",
            "billing_state": "UNKNOWN",
            "evaluation_state": "UNKNOWN",
            "deletion_state": "NOT_FOUND",
            "terminal_local_private_state": False,
        }

    raw_status = str(account.get("status") or "").strip()
    if raw_status == "active":
        account_state = "ACTIVE"
        deletion_state = "NONE"
    elif raw_status == "deletion_pending":
        account_state = "DELETION_REQUESTED_OR_IN_PROGRESS"
        deletion_state = "PENDING"
    elif raw_status == "deletion_failed":
        account_state = "DELETION_FAILED"
        deletion_state = "FAILED"
    elif raw_status == "deleted_pending_revocation":
        account_state = "DELETED_PENDING_EXTERNAL_REVOCATION"
        deletion_state = "PENDING"
    elif raw_status == "deleted":
        # Current privacy contract cannot prove external/provider completion merely
        # from this raw status value.
        account_state = "UNKNOWN_DELETION_COMPLETION"
        deletion_state = "UNKNOWN"
    else:
        account_state = "UNKNOWN"
        deletion_state = "UNKNOWN" if raw_status else "NONE"

    plan = str(account.get("plan") or "").strip()
    subscription = str(account.get("subscription_status") or "").strip()
    if plan == "pro" and subscription in {"active", "trial", "grace_period", "cancelled"}:
        billing_state = f"PRO_{subscription.upper()}"
    elif plan == "expired" or subscription == "expired":
        billing_state = "EXPIRED"
    elif subscription == "none":
        billing_state = "NONE"
    elif plan in {"pilot", "evaluation"}:
        billing_state = "NON_PRO_PRODUCT_STATE"
    else:
        billing_state = "UNKNOWN"

    evaluation = str(account.get("evaluation_status") or "").strip()
    evaluation_state = evaluation if evaluation else "UNKNOWN"

    return {
        "account_state": account_state,
        "raw_account_status": raw_status or None,
        "billing_state": billing_state,
        "raw_plan": plan or None,
        "raw_subscription_status": subscription or None,
        "evaluation_state": evaluation_state,
        "deletion_state": deletion_state,
        "terminal_local_private_state": raw_status == "deleted_pending_revocation",
    }


def deletion_allows_account_mutation(account: dict | None) -> bool:
    """Whether ordinary account-owned mutation may proceed under local lifecycle.

    This is a lifecycle contract only; callers/owners decide how to enforce it.
    Unknown/deletion states fail closed.
    """
    if not account:
        return False
    status = str(account.get("status") or "").strip()
    return status == "active"


def transition_contract() -> dict:
    """Repository-proven account.status transitions only.

    Billing and Evaluation changes are deliberately reported as orthogonal axes,
    not invented account.status transitions.
    """
    return {
        "states": {
            "active": "PROVEN",
            "deletion_pending": "PROVEN_BY_PRIVACY_CANDIDATE",
            "deletion_failed": "PROVEN_BY_PRIVACY_CANDIDATE",
            "deleted_pending_revocation": "PROVEN_BY_PRIVACY_CANDIDATE",
            "deleted": "LEGACY_RAW_VALUE_COMPLETION_UNPROVEN",
        },
        "transitions": [
            {"from": "active", "to": "deletion_pending", "authority": "CUSTOMER_REQUEST_VIA_PRIVACY_API"},
            {"from": "deletion_pending", "to": "deleted_pending_revocation", "authority": "LOCAL_PRIVACY_TRANSACTION_SUCCESS"},
            {"from": "deletion_pending", "to": "deletion_failed", "authority": "LOCAL_PRIVACY_TRANSACTION_FAILURE"},
            {"from": "deletion_failed", "to": "deletion_pending", "authority": "IDEMPOTENT_CUSTOMER_RETRY"},
        ],
        "completion_to_deleted": "UNKNOWN_EXTERNAL_OWNER_CONTRACT",
        "billing_axis_is_account_status": False,
        "evaluation_axis_is_account_status": False,
    }
