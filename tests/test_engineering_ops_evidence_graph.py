from engineering_ops_evidence_graph import EvidenceClaim, EvidenceDependency, classify_claim

OLD_407 = "1d0e176004291f06be5a48f69950025930395e54"
NEW_407 = "b92514440ab215b53b32bf22b4510b51f205edf1"
HEAD_408 = "ffb6c6e299adefe7ca743eedcaf4532a9cf2c8aa"
TREE_416 = "e18b424a2a536ed746e3d9c153964c64222536db"


def test_only_moved_dependency_invalidates_claim():
    claim = EvidenceClaim(
        claim_id="#416",
        exact_tree_sha=TREE_416,
        dependencies=(
            EvidenceDependency("PR", "407", OLD_407),
            EvidenceDependency("PR", "408", HEAD_408),
        ),
        gate_run_ids=(32896377357, 32896377690),
    )
    result = classify_claim(
        claim,
        current_dependencies={
            ("PR", "407"): NEW_407,
            ("PR", "408"): HEAD_408,
        },
    )
    assert result.state == "STALE"
    assert any("PR:407" in value for value in result.invalidated_by)
    assert any("PR:408" in value for value in result.preserved_dependencies)


def test_unchanged_claim_remains_current():
    claim = EvidenceClaim(
        claim_id="unrelated",
        exact_tree_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        dependencies=(EvidenceDependency("PR", "408", HEAD_408),),
    )
    result = classify_claim(
        claim,
        current_dependencies={("PR", "408"): HEAD_408},
    )
    assert result.state == "CURRENT"


def test_missing_lineage_is_needs_recheck():
    claim = EvidenceClaim(
        claim_id="unknown-lineage",
        exact_tree_sha=TREE_416,
        dependencies=(EvidenceDependency("PR", "999", OLD_407),),
    )
    result = classify_claim(claim, current_dependencies={})
    assert result.state == "NEEDS_RECHECK"


def test_missing_exact_tree_is_needs_recheck():
    claim = EvidenceClaim(
        claim_id="no-tree",
        exact_tree_sha=None,
        dependencies=(EvidenceDependency("PR", "407", OLD_407),),
    )
    result = classify_claim(
        claim,
        current_dependencies={("PR", "407"): NEW_407},
    )
    assert result.state == "NEEDS_RECHECK"
