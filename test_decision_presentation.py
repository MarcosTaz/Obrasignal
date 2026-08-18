from decision_presentation import present_decision


def test_present_decision_does_not_invent_missing_data():
    result = present_decision(None)

    assert result["status"] == "SEM DECISÃO"
    assert result["score"] is None
    assert result["lines"] == []


def test_present_decision_exposes_explainable_layers():
    result = present_decision({
        "decision": "QUALIFIED",
        "reason": "cumpre perfil e regras económicas",
        "score": 91,
        "confidence": 80,
        "rule_version": "test-v1",
        "decided_at": "2026-08-18T20:00:00+00:00",
        "features": {
            "profile_score": 86,
            "lot_score": 78,
            "lot_id": "LOT-1",
            "geography": {"score": 5, "reason": "cidade prioritária"},
            "capability_evidence": {
                "evidence_count": 2,
                "reason": "foram encontradas capacidades da empresa na descrição",
                "matched_services": ["estruturas metálicas", "coberturas"],
            },
            "economic_fit": {
                "status": "FAVOURABLE",
                "score": 100,
                "reason": "a oportunidade cumpre as regras económicas definidas pela empresa",
            },
            "hard_capability_blockers": [],
        },
    })

    assert result["status"] == "QUALIFIED"
    assert result["score"] == 91
    labels = [line["label"] for line in result["lines"]]
    assert labels == ["Perfil da empresa", "Lote", "Geografia", "Capacidade", "Economic Fit"]
    assert result["lines"][2]["detail"] == "cidade prioritária"
    assert "estruturas metálicas" in result["lines"][3]["detail"]
    assert result["lines"][4]["value"] == "100/100"


def test_present_decision_shows_hard_blockers():
    result = present_decision({
        "decision": "REJECTED",
        "reason": "CAPABILITY_BLOCKER",
        "features": {
            "hard_capability_blockers": ["procedimento excluído: AJUSTE_DIRETO", "CPV fora das famílias aceites pela empresa"],
        },
    })

    blocker = next(line for line in result["lines"] if line["label"] == "Bloqueios")
    assert blocker["value"] == "2"
    assert "CPV fora" in blocker["detail"]
