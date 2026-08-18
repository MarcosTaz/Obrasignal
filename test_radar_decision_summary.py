from radar_decision_summary import summarize_decision


def test_missing_decision_has_explicit_fallback():
    result = summarize_decision(None)
    assert result["status"] == "SEM DECISÃO"
    assert result["class_name"] == "low"
    assert "não existe" in result["reason"]


def test_qualified_decision_is_high_priority():
    result = summarize_decision({
        "decision": "QUALIFIED",
        "reason": "cumpre perfil e regras económicas",
        "score": 88,
        "rule_version": "test-v1",
    })
    assert result["status"] == "QUALIFIED"
    assert result["class_name"] == "hot"
    assert result["score"] == 88
    assert result["rule_version"] == "test-v1"


def test_rejected_decision_is_low_priority():
    result = summarize_decision({
        "decision": "REJECTED",
        "reason": "CAPABILITY_BLOCKER",
    })
    assert result["class_name"] == "low"
