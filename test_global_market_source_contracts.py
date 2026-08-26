from global_market_source_contracts import (
    BRAZIL,
    CANADA,
    CHILE,
    SOURCE_CONTRACTS,
    UNITED_STATES,
    technical_promotion_eligible,
)


def test_priority_a_contract_registry_is_complete_and_fail_closed():
    assert set(SOURCE_CONTRACTS) == {"Brazil", "Canada", "United States", "Chile"}
    assert not any(technical_promotion_eligible(contract) for contract in SOURCE_CONTRACTS.values())


def test_canada_preserves_native_identity_time_and_no_fabricated_value():
    assert CANADA.identity == "solicitationNumber-numeroSollicitation"
    assert "UTC-05:00" in CANADA.timezone
    assert "emit empty" in CANADA.value
    assert CANADA.tests.duplicate == "PROVEN"
    assert CANADA.tests.cancelled == "PROVEN"
    assert CANADA.live_evidence == "PROVEN"
    assert CANADA.tests.extra_field == "UNKNOWN"
    assert technical_promotion_eligible(CANADA) is False


def test_us_live_green_does_not_fake_complete_matrix():
    assert UNITED_STATES.identity == "NoticeId"
    assert "NAICS" in UNITED_STATES.taxonomy
    assert "never current tender value" in UNITED_STATES.value
    assert UNITED_STATES.live_evidence == "PROVEN"
    assert UNITED_STATES.tests.malformed == "PROVEN"
    assert UNITED_STATES.tests.empty == "UNKNOWN"
    assert UNITED_STATES.contract_state == "TECHNICAL_PARTIAL"
    assert technical_promotion_eligible(UNITED_STATES) is False


def test_chile_preserves_credential_rate_limit_and_hidden_amount_gates():
    assert "MERCADOPUBLICO_TICKET" in CHILE.auth_requirement
    assert "429" in CHILE.rate_limit
    assert "VisibilidadMonto" in CHILE.value
    assert CHILE.tests.updated == "PROVEN"
    assert CHILE.tests.cancelled == "PROVEN"
    assert CHILE.tests.timezone == "UNKNOWN"
    assert CHILE.live_evidence == "BLOCKED"
    assert CHILE.contract_state == "TECHNICAL_BLOCKED"


def test_brazil_does_not_inherit_historical_prebuilt_claim_as_code_or_contract_green():
    assert "NO_CODE" in BRAZIL.exact_gap
    assert BRAZIL.contract_state == "TECHNICAL_BLOCKED"
    assert BRAZIL.live_evidence == "BLOCKED"
    assert all(
        value == "UNKNOWN"
        for value in (
            BRAZIL.tests.normal,
            BRAZIL.tests.empty,
            BRAZIL.tests.partial,
            BRAZIL.tests.malformed,
            BRAZIL.tests.duplicate,
            BRAZIL.tests.updated,
            BRAZIL.tests.cancelled,
            BRAZIL.tests.pagination,
            BRAZIL.tests.restart,
            BRAZIL.tests.cursor_boundary,
            BRAZIL.tests.timezone,
            BRAZIL.tests.unknown_field,
            BRAZIL.tests.extra_field,
        )
    )


def test_http_or_live_success_is_not_source_contract_completeness():
    assert CANADA.live_evidence == "PROVEN"
    assert UNITED_STATES.live_evidence == "PROVEN"
    assert technical_promotion_eligible(CANADA) is False
    assert technical_promotion_eligible(UNITED_STATES) is False
