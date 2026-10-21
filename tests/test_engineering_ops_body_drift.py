from engineering_ops_body_drift import classify_body_drift

HEAD = "d628fc0a5e7d347b9e502c938d3cf118b6a055f7"
OLD = "1d0e176004291f06be5a48f69950025930395e54"
DEP = "ffb6c6e299adefe7ca743eedcaf4532a9cf2c8aa"
DEP_NEW = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def test_stale_head():
    result = classify_body_drift(
        pr_number=407,
        body=f"current exact HEAD `{OLD}`",
        actual_head=HEAD,
        actual_dependency_heads={},
    )
    assert result.state == "BODY_STALE_HEAD"


def test_stale_dependency():
    result = classify_body_drift(
        pr_number=413,
        body=f"current exact HEAD `{HEAD}`\n#408 CURRENT `{DEP}`",
        actual_head=HEAD,
        actual_dependency_heads={408: DEP_NEW},
    )
    assert result.state == "BODY_STALE_DEPENDENCY"


def test_stale_evidence():
    result = classify_body_drift(
        pr_number=407,
        body=f"current exact HEAD `{HEAD}`\nrun `12345678`",
        actual_head=HEAD,
        actual_dependency_heads={},
        current_evidence_run_ids={87654321},
    )
    assert result.state == "BODY_STALE_EVIDENCE"


def test_current_body():
    result = classify_body_drift(
        pr_number=407,
        body=f"current exact HEAD `{HEAD}`\nrun `87654321`",
        actual_head=HEAD,
        actual_dependency_heads={},
        current_evidence_run_ids={87654321},
    )
    assert result.state == "BODY_CURRENT"


def test_unknown_without_live_head():
    result = classify_body_drift(
        pr_number=407,
        body=f"current exact HEAD `{HEAD}`",
        actual_head=None,
        actual_dependency_heads={},
    )
    assert result.state == "UNKNOWN"
