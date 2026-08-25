from engineering_ops import (
    EVIDENCE_STATES,
    GATE_STATES,
    REQUIRED_STATUS_FIELDS,
    STATUS_VALUES,
    candidate_record,
    classify_reference,
    extract_declared_head,
    extract_declared_main,
    extract_dependency_refs,
    normalize_workflow_runs,
    report_snapshot,
    sha_matches,
)


MAIN = "66d43f6fd51cf9cea08016dad335aaa04b711a24"
HEAD_238_ACTUAL = "6519b9f368a229da2b2787caf178f8ef956bda5b"
HEAD_238_BODY = "1e8005e68d41a8c45130693ebda28e1a57422256"
HEAD_319 = "52e3ba5474d3e388735715db051e87eafb14c90a"


def test_status_contract_is_bounded_and_required_fields_exist():
    assert STATUS_VALUES == (
        "ACTIVE",
        "NEXT",
        "WAIT",
        "GREEN",
        "RED",
        "STALE",
        "BLOCKED_EXTERNAL",
        "BLOCKED_OWNER",
        "READY",
        "HANDOFF_READY",
        "CANONICAL_NEXT",
        "SUPERSEDED",
        "UNKNOWN",
    )
    assert EVIDENCE_STATES == ("CURRENT", "STALE", "SUPERSEDED", "UNKNOWN")
    assert "PASS" in GATE_STATES
    assert "HISTORICAL" in GATE_STATES
    assert REQUIRED_STATUS_FIELDS == (
        "owner",
        "exact_head",
        "base",
        "main_sha",
        "evidence",
        "reason",
        "reopen_condition",
    )


def test_sha_matching_accepts_bounded_short_prefix_and_rejects_drift():
    assert sha_matches("6519b9f3", HEAD_238_ACTUAL)
    assert not sha_matches("1e8005e6", HEAD_238_ACTUAL)
    assert not sha_matches("6519", HEAD_238_ACTUAL)


def test_reference_unknown_never_becomes_current():
    state = classify_reference(None, HEAD_238_ACTUAL, subject="candidate")
    assert state.state == "UNKNOWN"
    assert state.declared is None


def test_extracts_declared_self_head_and_main_from_realistic_body_shape():
    body = f"""
### CURRENT EXACT TRUTH
- canonical main: `{MAIN}`
- current owner HEAD: `{HEAD_238_BODY}`
"""
    assert extract_declared_head(body) == HEAD_238_BODY
    assert extract_declared_main(body) == MAIN


def test_extracts_explicit_pr_sha_dependencies_without_bare_pr_mentions():
    body = f"""
### EXACT CURRENT INPUTS
- main `{MAIN}`
- CORE R2 #314 `52641ebee4b25c2bfddcd2a56282b9ad5e746bcf`
- #240 `d9effd41c54a50f567fb5d446a24b7bc3859b3bf`
- #238 CURRENT `2aa332112bf0497b698bfb8dabafcca4562ca1bd`
- CURRENT ALL-UP C HEAD `{HEAD_319}`
#281 remains OPEN but has no pinned SHA.
"""
    refs = extract_dependency_refs(body, self_pr=319)
    assert [(item["pr"], item["declared_sha"][:8]) for item in refs] == [
        (238, "2aa33211"),
        (240, "d9effd41"),
        (314, "52641ebe"),
    ]


def test_wrong_head_green_is_historical_stale_not_current_pass():
    runs = [
        {
            "name": "ObraSignal Quality",
            "id": 1,
            "head_sha": HEAD_238_BODY,
            "status": "completed",
            "conclusion": "success",
        }
    ]
    normalized = normalize_workflow_runs(runs, candidate_head=HEAD_238_ACTUAL)
    assert normalized[0]["gate_state"] == "HISTORICAL"
    assert normalized[0]["evidence_state"] == "STALE"
    assert normalized[0]["exact_head"] is False


def test_exact_head_success_is_current_pass_but_not_readiness():
    runs = [
        {
            "name": "ObraSignal Quality",
            "id": 2,
            "head_sha": HEAD_238_ACTUAL,
            "status": "completed",
            "conclusion": "success",
        }
    ]
    normalized = normalize_workflow_runs(runs, candidate_head=HEAD_238_ACTUAL)
    assert normalized[0]["gate_state"] == "PASS"
    assert normalized[0]["evidence_state"] == "CURRENT"
    assert "no product/readiness authority" in normalized[0]["proves"]


def test_skipped_exact_head_run_is_not_run_not_red():
    runs = [
        {
            "name": "Path Filtered",
            "id": 3,
            "head_sha": HEAD_238_ACTUAL,
            "status": "completed",
            "conclusion": "skipped",
        }
    ]
    normalized = normalize_workflow_runs(runs, candidate_head=HEAD_238_ACTUAL)
    assert normalized[0]["gate_state"] == "NOT_RUN"
    assert normalized[0]["evidence_state"] == "CURRENT"


def test_pr_body_self_head_drift_classifies_stale_fail_closed():
    body = f"""
- canonical main: `{MAIN}`
- current owner HEAD: `{HEAD_238_BODY}`
"""
    record = candidate_record(
        {
            "number": 238,
            "title": "storage",
            "body": body,
            "head_sha": HEAD_238_ACTUAL,
            "base_sha": MAIN,
            "base_ref": "main",
            "draft": True,
            "mergeable": True,
        },
        main_sha=MAIN,
        actual_heads={238: HEAD_238_ACTUAL},
    )
    assert record["status"] == "STALE"
    assert record["owner"] == "UNKNOWN"
    assert record["evidence"]["self_head"]["state"] == "STALE"
    assert "PR body HEAD" in record["reason"]


def test_downstream_dependency_movement_invalidates_only_dependent_candidate():
    body = f"""
- main `{MAIN}`
- #238 CURRENT `2aa332112bf0497b698bfb8dabafcca4562ca1bd`
- CURRENT ALL-UP C HEAD `{HEAD_319}`
"""
    record = candidate_record(
        {
            "number": 319,
            "title": "all-up",
            "body": body,
            "head_sha": HEAD_319,
            "base_sha": MAIN,
            "base_ref": "main",
            "draft": True,
            "mergeable": True,
        },
        main_sha=MAIN,
        actual_heads={238: HEAD_238_ACTUAL, 319: HEAD_319},
    )
    assert record["status"] == "STALE"
    assert record["evidence"]["self_head"]["state"] == "CURRENT"
    dependency = record["evidence"]["dependencies"][0]
    assert dependency["pr"] == 238
    assert dependency["state"] == "STALE"


def test_missing_main_or_collection_failure_never_becomes_green():
    report = report_snapshot(
        {
            "main_sha": None,
            "pull_requests": [
                {
                    "number": 1,
                    "title": "unknown",
                    "body": "",
                    "head_sha": HEAD_319,
                    "base_sha": MAIN,
                    "base_ref": "main",
                }
            ],
            "collection_errors": {"1": "GitHub unavailable"},
        }
    )
    assert report["overall"] == "UNKNOWN"
    assert report["candidates"][0]["status"] == "UNKNOWN"
    assert "never GREEN" in report["failure_semantics"]


def test_machine_readable_manifest_matches_runtime_contract():
    import json
    from pathlib import Path

    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "engineering_ops_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert tuple(manifest["status_values"]) == STATUS_VALUES
    assert tuple(manifest["evidence_states"]) == EVIDENCE_STATES
    assert tuple(manifest["gate_states"]) == GATE_STATES
    assert tuple(manifest["required_candidate_fields"]) == REQUIRED_STATUS_FIELDS
    assert manifest["failure_semantics"]["may_mark_green"] is False


def test_dependency_parser_stops_at_next_pr_token():
    body = """
## Persistence / Integration handoff — REQUIRED
Integration Lab #319 must use current #329 input `d8b14d5656c1029d0ce0f6da208b8491640e5540` and current #238 persistence guards together.
"""
    refs = extract_dependency_refs(body, self_pr=329)
    # #319 has no SHA in its own segment; #329 is self; #238 has no SHA.
    assert refs == []


def test_diagnostic_historical_examples_do_not_become_current_dependencies():
    body = """
## Current known drift that motivated this slice
- PR #238 actual HEAD observed as `6519b9f368a229da2b2787caf178f8ef956bda5b`, while its body declared current owner HEAD `1e8005e68d41a8c45130693ebda28e1a57422256`.
- PR #319 still pinned #238 at `2aa332112bf0497b698bfb8dabafcca4562ca1bd`.
"""
    assert extract_dependency_refs(body, self_pr=407) == []
    assert extract_declared_head(body, self_pr=407) is None


def test_non_pr_hash_number_can_be_ignored_without_false_unknown():
    own_head = "35b273d2fe9e96ebe5eeeb0cdb8b9142213284cb"
    body = f"""
- canonical main `{MAIN}`
- current owner HEAD `{own_head}`
- ObraSignal Quality #2030 exact HEAD `{own_head}`: SUCCESS.
"""
    record = candidate_record(
        {
            "number": 382,
            "title": "quality",
            "body": body,
            "head_sha": own_head,
            "base_sha": MAIN,
            "base_ref": "main",
        },
        main_sha=MAIN,
        actual_heads={382: own_head},
        ignored_dependency_prs={2030},
    )
    assert record["status"] == "ACTIVE"
    assert record["evidence"]["dependencies"] == []
