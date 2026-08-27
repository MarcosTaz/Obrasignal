"""Integration-only extension of the exact Persistence #238 storage registry.

The canonical owner remains storage_contract_base (#238 exact blob). This wrapper
mutates that one registry in-place for current-spine acceptance; it is not a
second persistence authority and is not proposed for merge as architecture.
"""
import storage_contract_base as _base
from storage_contract_base import *  # noqa: F401,F403

# Watchlist #150 is an additive extension of the already-canonical workflow table.
_workflow = _base.STARTUP_CONTRACTS["opportunity_workflow"]
_base.STARTUP_CONTRACTS["opportunity_workflow"] = _base.TableContract(
    _workflow.owner,
    frozenset(set(_workflow.required_columns) | {"priority", "saved_at"}),
    tenant_column=_workflow.tenant_column,
    unique_keys=_workflow.unique_keys,
    required_indexes=tuple(dict.fromkeys((*_workflow.required_indexes,
        "idx_opportunity_workflow_account_saved",
        "idx_opportunity_workflow_account_status_priority",
    ))),
)
_base.REGISTERED_ADDITIVE_MIGRATIONS["opportunity_workflow"] = ("priority", "saved_at")

# Pursuit Workspace remains candidate/PREBUILD storage until product adoption.
_base.PREBUILD_CONTRACTS.update({
    "pursuit_workspaces": _base.TableContract(
        "Pursuit Workspace / pursuit_workspace",
        frozenset({
            "workspace_id", "account_id", "opportunity_id", "owner_id",
            "workspace_status", "review_state", "submission_state",
            "created_at", "updated_at",
        }),
        tenant_column="account_id",
        unique_keys=(("account_id", "opportunity_id"),),
        required_indexes=("idx_pursuit_workspace_account",),
    ),
    "pursuit_workspace_blockers": _base.TableContract(
        "Pursuit Workspace / pursuit_workspace",
        frozenset({
            "blocker_id", "workspace_id", "title", "status", "severity",
            "created_by", "created_at", "resolved_at",
        }),
        required_indexes=("idx_pursuit_blocker_workspace",),
    ),
    "pursuit_workspace_notes": _base.TableContract(
        "Pursuit Workspace / pursuit_workspace",
        frozenset({"note_id", "workspace_id", "body", "created_by", "created_at"}),
        required_indexes=("idx_pursuit_note_workspace",),
    ),
    "pursuit_workspace_questions": _base.TableContract(
        "Pursuit Workspace / pursuit_workspace",
        frozenset({
            "question_id", "workspace_id", "question", "status", "source_ref",
            "owner_id", "created_at", "updated_at",
        }),
        required_indexes=("idx_pursuit_question_workspace",),
    ),
})

# Rebuild the single owner map after extending the exact #238 registries.
_base.KNOWN_TABLE_OWNERS = {
    **_base.STARTUP_CONTRACTS,
    **_base.RUNTIME_CONTRACTS,
    **_base.PREBUILD_CONTRACTS,
    **_base.TEST_ONLY_CONTRACTS,
}
KNOWN_TABLE_OWNERS = _base.KNOWN_TABLE_OWNERS
STARTUP_CONTRACTS = _base.STARTUP_CONTRACTS
PREBUILD_CONTRACTS = _base.PREBUILD_CONTRACTS
REGISTERED_ADDITIVE_MIGRATIONS = _base.REGISTERED_ADDITIVE_MIGRATIONS
