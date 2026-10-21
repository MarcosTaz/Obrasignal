from international_portfolio_states import apply_state_contract


def _result():
    return {
        "countries": [],
        "summary": {},
        "contradictions": [],
        "missing_integrations": [],
    }


def _source(portfolio, key):
    return next(row for row in portfolio if row["SOURCE"] == key)


def test_exact_head_quality_and_live_promote_current_candidate_only(tmp_path):
    head = "1" * 40
    main = "2" * 40
    evidence = {
        "schema_version": 1,
        "canonical_main_sha": main,
        "candidates": [
            {
                "pr": 999,
                "head": head,
                "base_main_sha": main,
                "quality": {"status": "SUCCESS", "run_id": 10, "head": head},
                "sources": [
                    {
                        "source": "ZZ_EXACT",
                        "country": "Testland",
                        "implemented": True,
                        "tested": True,
                        "runtime_wired": False,
                        "ready": False,
                        "planned": True,
                        "gated_rights": True,
                        "gated_machine_access": False,
                        "gated_credential": False,
                        "gated_completeness": False,
                        "tech_lab": False,
                        "live": {
                            "status": "SUCCESS",
                            "run_id": 11,
                            "head": head,
                            "result_kind": "EMPTY_VALID_RESULT",
                        },
                    }
                ],
            }
        ],
        "supersession": [],
    }
    audited = apply_state_contract(_result(), tmp_path, evidence=evidence)
    row = _source(audited["source_portfolio"], "ZZ_EXACT")
    assert row["IMPLEMENTED"] is True
    assert row["TESTED"] is True
    assert row["LIVE_VALIDATED"] is True
    assert row["LIVE_RESULT_KIND"] == "EMPTY_VALID_RESULT"
    assert row["PLANNED"] is True
    assert row["GATED_RIGHTS"] is True
    assert row["QUALITY_RUNS"] == [10]
    assert row["LIVE_RUNS"] == [11]
    assert audited["candidate_evidence"]["rejected_proofs"] == []


def test_historical_or_mismatched_head_cannot_promote_tested_or_live(tmp_path):
    head = "3" * 40
    old = "4" * 40
    main = "5" * 40
    evidence = {
        "schema_version": 1,
        "canonical_main_sha": main,
        "candidates": [
            {
                "pr": 998,
                "head": head,
                "base_main_sha": main,
                "quality": {"status": "SUCCESS", "run_id": 20, "head": old},
                "sources": [
                    {
                        "source": "ZZ_STALE",
                        "country": "Testland",
                        "implemented": True,
                        "tested": True,
                        "live": {"status": "SUCCESS", "run_id": 21, "head": old},
                    }
                ],
            }
        ],
        "supersession": [],
    }
    audited = apply_state_contract(_result(), tmp_path, evidence=evidence)
    row = _source(audited["source_portfolio"], "ZZ_STALE")
    assert row["IMPLEMENTED"] is True
    assert row["TESTED"] is False
    assert row["LIVE_VALIDATED"] is False
    rejected = audited["candidate_evidence"]["rejected_proofs"]
    assert any("quality_head_mismatch_or_failure" in item for item in rejected)
    assert any("live_head_mismatch_or_failure" in item for item in rejected)


def test_stale_main_candidate_cannot_promote_execution_proof(tmp_path):
    head = "6" * 40
    main = "7" * 40
    stale_main = "8" * 40
    evidence = {
        "schema_version": 1,
        "canonical_main_sha": main,
        "candidates": [
            {
                "pr": 997,
                "head": head,
                "base_main_sha": stale_main,
                "quality": {"status": "SUCCESS", "run_id": 30, "head": head},
                "sources": [
                    {
                        "source": "ZZ_OLD_BASE",
                        "country": "Testland",
                        "implemented": True,
                        "tested": True,
                        "live": {"status": "SUCCESS", "run_id": 31, "head": head},
                    }
                ],
            }
        ],
        "supersession": [],
    }
    audited = apply_state_contract(_result(), tmp_path, evidence=evidence)
    row = _source(audited["source_portfolio"], "ZZ_OLD_BASE")
    assert row["IMPLEMENTED"] is True
    assert row["TESTED"] is False
    assert row["LIVE_VALIDATED"] is False
    assert any("stale_main" in item for item in audited["candidate_evidence"]["rejected_proofs"])


def test_requested_state_vocabulary_is_present(tmp_path):
    audited = apply_state_contract(_result(), tmp_path, evidence={"schema_version": 1, "canonical_main_sha": "9" * 40, "candidates": [], "supersession": []})
    required = {
        "REGISTERED", "IMPLEMENTED", "TESTED", "LIVE_VALIDATED", "RUNTIME_WIRED",
        "PRODUCTION_ACTIVE", "READY", "PLANNED", "GATED_RIGHTS",
        "GATED_MACHINE_ACCESS", "GATED_CREDENTIAL", "GATED_COMPLETENESS",
        "TECH_LAB", "SUPERSEDED",
    }
    for row in audited["source_portfolio"]:
        assert required <= set(row)
