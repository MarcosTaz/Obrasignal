import sqlite3


COMPANY_E_ORACLE = {
    "company": "synthetic-zero-opportunity-electrical",
    "true_available_opportunities": [],
    "true_outcomes": [],
    "true_economic_value": 0,
}

UNRELATED_MARKET_ROWS = [
    {
        "source": "ORACLE-SYNTHETIC",
        "external_id": "ZERO-1",
        "title": "Serviço de catering para eventos municipais",
        "description": "Fornecimento e confeção de refeições e coffee breaks",
        "country": "PRT",
        "cpv": "55520000",
        "value_numeric": 120000,
        "deadline": "2099-01-01",
    },
    {
        "source": "ORACLE-SYNTHETIC",
        "external_id": "ZERO-2",
        "title": "Fornecimento de mobiliário administrativo",
        "description": "Mesas, cadeiras e armários para serviços administrativos",
        "country": "PRT",
        "cpv": "39130000",
        "value_numeric": 180000,
        "deadline": "2099-01-01",
    },
]


def test_company_e_zero_opportunity_remains_valid_zero_value_result():
    from account_registry import ensure_account, get_account
    from company_profile import derive_profile
    from evaluation_policy import evaluation_metrics, record_evaluation_event
    from opportunity_match_pipeline import evaluate_and_record

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    account_id = COMPANY_E_ORACLE["company"]
    try:
        ensure_account(conn, account_id)
        record_evaluation_event(conn, account_id, "profile_ready")
        profile = derive_profile(
            "instalações elétricas",
            {
                "activity": "instalações elétricas",
                "countries": ["PRT"],
                "cpv_prefixes": ["4531"],
                "keywords": ["instalação elétrica", "quadros elétricos", "iluminação"],
            },
        )
        profile["account_id"] = account_id

        evaluations = [
            evaluate_and_record(conn, row, profile=profile, account_id=account_id)
            for row in UNRELATED_MARKET_ROWS
        ]

        assert COMPANY_E_ORACLE["true_available_opportunities"] == []
        assert all(result["decision"] == "REJECT" for result in evaluations)
        assert all(result["profile_score"] <= 35 for result in evaluations)

        event_names = {
            row[0]
            for row in conn.execute(
                "SELECT event_name FROM evaluation_events WHERE account_id=?",
                (account_id,),
            ).fetchall()
        }
        assert "market_data_available" in event_names
        assert "first_shortlist_generated" not in event_names

        metrics = evaluation_metrics(conn, get_account(conn, account_id))
        assert metrics["VALUE_EXPOSURE_RATE"] == 0
        assert metrics["exposure_event_count"] == 0
        assert metrics["TIME_TO_FIRST_VALUE_SECONDS"] is None
        assert metrics["TIME_TO_FIRST_VERIFIED_VALUE_SECONDS"] is None
        assert metrics["FIRST_VERIFIED_VALUE_RECORDED"] is False
        assert metrics["measured_value_event_count"] == 0
        assert metrics["estimated_value_event_count"] == 0

        workflow_rows = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='opportunity_workflow'"
        ).fetchone()[0]
        if workflow_rows:
            assert conn.execute("SELECT COUNT(*) FROM opportunity_workflow WHERE account_id=?", (account_id,)).fetchone()[0] == 0
    finally:
        conn.close()


def test_zero_value_web_state_is_a_truthful_terminal_result_not_a_prompt_to_manufacture_signal():
    from radar_web import render_radar_page

    html = render_radar_page([], minscore=0)
    assert "RESULTADO VÁLIDO · ZERO-VALUE" in html
    assert "Nada material encontrado neste momento." in html
    assert "Não baixamos critérios nem fabricamos uma oportunidade" in html
    assert "manter o perfil correto" in html


def test_filter_empty_state_does_not_claim_zero_value_or_force_lower_thresholds():
    from radar_web import render_radar_page

    html = render_radar_page([], minscore=75)
    assert "FILTRO ATUAL" in html
    assert "Nenhuma oportunidade neste filtro." in html
    assert "Isto não significa que exista valor escondido." in html
    assert "Altera o filtro apenas se os critérios comerciais da empresa também justificarem" in html
    assert "RESULTADO VÁLIDO · ZERO-VALUE" not in html
