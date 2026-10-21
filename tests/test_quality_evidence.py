from __future__ import annotations

import pytest

from quality_evidence import EvidenceContractError, audit_manifest


CANDIDATE = "a" * 40
TREE = "b" * 40
MAIN = "c" * 40
OLD = "d" * 40
OWNER_CURRENT = "e" * 40
OWNER_OLD = "f" * 40


def manifest(**overrides):
    value = {
        "candidate_sha": CANDIDATE,
        "candidate_tree_sha": TREE,
        "base_sha": MAIN,
        "current_main_sha": MAIN,
        "required_workflows": ["ObraSignal Quality"],
        "runs": [
            {
                "workflow": "ObraSignal Quality",
                "head_sha": CANDIDATE,
                "tree_sha": TREE,
                "status": "completed",
                "conclusion": "success",
                "run_id": 100,
            }
        ],
        "owner_inputs": [],
    }
    value.update(overrides)
    return value


def issue_codes(result):
    return {issue["code"] for issue in result["issues"]}


def test_green_requires_exact_completed_success():
    result = audit_manifest(manifest())

    assert result["verdict"] == "GREEN"
    assert result["workflows"] == {"ObraSignal Quality": "GREEN"}
    assert result["issues"] == []


def test_historical_green_is_not_current_green():
    result = audit_manifest(
        manifest(
            runs=[
                {
                    "workflow": "ObraSignal Quality",
                    "head_sha": OLD,
                    "status": "completed",
                    "conclusion": "success",
                    "run_id": 99,
                }
            ]
        )
    )

    assert result["verdict"] == "NOT_GREEN"
    assert issue_codes(result) == {"HISTORICAL_GREEN"}


def test_missing_path_filtered_workflow_is_not_run_not_green():
    result = audit_manifest(manifest(required_workflows=["JWT"], runs=[]))

    assert result["workflows"]["JWT"] == "NOT_RUN"
    assert issue_codes(result) == {"NOT_RUN"}


def test_in_progress_exact_head_run_is_not_green():
    result = audit_manifest(
        manifest(
            runs=[
                {
                    "workflow": "ObraSignal Quality",
                    "head_sha": CANDIDATE,
                    "status": "in_progress",
                    "conclusion": None,
                    "run_id": 101,
                }
            ]
        )
    )

    assert issue_codes(result) == {"IN_PROGRESS"}


def test_skipped_required_workflow_is_not_green():
    result = audit_manifest(
        manifest(
            runs=[
                {
                    "workflow": "ObraSignal Quality",
                    "head_sha": CANDIDATE,
                    "status": "completed",
                    "conclusion": "skipped",
                    "run_id": 101,
                }
            ]
        )
    )

    assert issue_codes(result) == {"SKIPPED"}


def test_failed_exact_head_run_is_red():
    result = audit_manifest(
        manifest(
            runs=[
                {
                    "workflow": "ObraSignal Quality",
                    "head_sha": CANDIDATE,
                    "status": "completed",
                    "conclusion": "failure",
                    "run_id": 101,
                }
            ]
        )
    )

    assert issue_codes(result) == {"RED"}


def test_candidate_based_on_stale_main_is_not_green():
    result = audit_manifest(manifest(current_main_sha=OLD))

    assert "STALE_MAIN" in issue_codes(result)


def test_owner_drift_invalidates_downstream_evidence():
    result = audit_manifest(
        manifest(
            owner_inputs=[
                {
                    "owner": "notifications/#329",
                    "current_sha": OWNER_CURRENT,
                    "evidence_sha": OWNER_OLD,
                }
            ]
        )
    )

    assert result["owner_inputs"]["notifications/#329"] == "OWNER_DRIFT"
    assert "OWNER_DRIFT" in issue_codes(result)


def test_wrong_tree_is_rejected_even_when_sha_field_claims_candidate():
    result = audit_manifest(
        manifest(
            runs=[
                {
                    "workflow": "ObraSignal Quality",
                    "head_sha": CANDIDATE,
                    "tree_sha": OLD,
                    "status": "completed",
                    "conclusion": "success",
                    "run_id": 101,
                }
            ]
        )
    )

    assert issue_codes(result) == {"WRONG_TREE"}


def test_newest_exact_head_run_wins_over_older_success():
    result = audit_manifest(
        manifest(
            runs=[
                {
                    "workflow": "ObraSignal Quality",
                    "head_sha": CANDIDATE,
                    "status": "completed",
                    "conclusion": "success",
                    "run_id": 100,
                },
                {
                    "workflow": "ObraSignal Quality",
                    "head_sha": CANDIDATE,
                    "status": "completed",
                    "conclusion": "failure",
                    "run_id": 101,
                },
            ]
        )
    )

    assert result["workflows"]["ObraSignal Quality"] == "RED"
    assert issue_codes(result) == {"RED"}


def test_duplicate_runs_without_run_ids_fail_closed_as_ambiguous():
    value = manifest(
        runs=[
            {
                "workflow": "ObraSignal Quality",
                "head_sha": CANDIDATE,
                "status": "completed",
                "conclusion": "success",
            },
            {
                "workflow": "ObraSignal Quality",
                "head_sha": CANDIDATE,
                "status": "completed",
                "conclusion": "success",
            },
        ]
    )

    with pytest.raises(EvidenceContractError, match="multiple runs"):
        audit_manifest(value)


def test_short_sha_is_rejected_to_prevent_prefix_collision():
    value = manifest(candidate_sha="deadbeef")

    with pytest.raises(EvidenceContractError, match="40-character"):
        audit_manifest(value)
