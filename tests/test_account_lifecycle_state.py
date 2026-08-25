from account_lifecycle_state import (
    deletion_allows_account_mutation,
    project_account_lifecycle,
    transition_contract,
)


def test_active_account_keeps_billing_and_evaluation_as_orthogonal_axes():
    state = project_account_lifecycle({
        "status": "active",
        "plan": "pro",
        "subscription_status": "cancelled",
        "evaluation_status": "PAID",
    })
    assert state["account_state"] == "ACTIVE"
    assert state["billing_state"] == "PRO_CANCELLED"
    assert state["evaluation_state"] == "PAID"
    assert state["deletion_state"] == "NONE"
    assert deletion_allows_account_mutation({"status": "active"}) is True


def test_deleted_pending_revocation_is_terminal_for_local_private_mutation():
    account = {
        "status": "deleted_pending_revocation",
        "plan": "expired",
        "subscription_status": "none",
        "evaluation_status": None,
    }
    state = project_account_lifecycle(account)
    assert state["account_state"] == "DELETED_PENDING_EXTERNAL_REVOCATION"
    assert state["deletion_state"] == "PENDING"
    assert state["terminal_local_private_state"] is True
    assert deletion_allows_account_mutation(account) is False


def test_raw_deleted_never_implies_complete_external_deletion():
    state = project_account_lifecycle({
        "status": "deleted",
        "plan": "expired",
        "subscription_status": "none",
    })
    assert state["account_state"] == "UNKNOWN_DELETION_COMPLETION"
    assert state["deletion_state"] == "UNKNOWN"
    assert state["terminal_local_private_state"] is False


def test_unknown_account_status_fails_closed():
    account = {"status": "future_state", "plan": "pro", "subscription_status": "active"}
    state = project_account_lifecycle(account)
    assert state["account_state"] == "UNKNOWN"
    assert state["deletion_state"] == "UNKNOWN"
    assert deletion_allows_account_mutation(account) is False


def test_contract_does_not_invent_billing_or_evaluation_account_states():
    contract = transition_contract()
    assert contract["billing_axis_is_account_status"] is False
    assert contract["evaluation_axis_is_account_status"] is False
    assert contract["completion_to_deleted"] == "UNKNOWN_EXTERNAL_OWNER_CONTRACT"
    transitions = {(item["from"], item["to"]) for item in contract["transitions"]}
    assert ("active", "deletion_pending") in transitions
    assert ("deletion_pending", "deleted_pending_revocation") in transitions
    assert all("pro" not in pair and "evaluation" not in pair for pair in transitions)
