from global_market_expansion_factory import HOLD_MONITORS
from global_market_hold_evidence import (
    AUSTRALIA,
    HOLD_EVIDENCE_OBSERVATIONS,
    INDIA,
    MEXICO,
    SOUTH_KOREA,
    reopen_trigger_satisfied,
)


def test_hold_evidence_only_attaches_to_current_hold_markets():
    assert set(HOLD_EVIDENCE_OBSERVATIONS) <= set(HOLD_MONITORS)


def test_south_korea_research_is_narrowed_to_credential_and_live_contract():
    assert SOUTH_KOREA.trigger_state == "TRIGGER_FALSE"
    assert "official REST OpenAPI" in SOUTH_KOREA.proven_now
    assert "construction-specific bid-notice operation" in SOUTH_KOREA.proven_now
    assert "published licence scope states no restrictions" in SOUTH_KOREA.proven_now
    assert "project KONEPS_SERVICE_KEY" in SOUTH_KOREA.missing_now
    assert reopen_trigger_satisfied("South Korea") is False


def test_australia_public_portal_does_not_fake_machine_reuse_green():
    assert AUSTRALIA.trigger_state == "TRIGGER_FALSE"
    assert "all open approaches to market are published on AusTender" in AUSTRALIA.proven_now
    assert "official production-safe machine-readable live ATM route" in AUSTRALIA.missing_now
    assert "source-scoped commercial reuse/redistribution terms for that route" in AUSTRALIA.missing_now
    assert reopen_trigger_satisfied("Australia") is False


def test_india_current_market_activity_does_not_authorize_captcha_bypass():
    assert INDIA.trigger_state == "TRIGGER_FALSE"
    assert "construction tenders are present in current results" in INDIA.proven_now
    assert "official broad machine-readable tender API/feed or bulk route" in INDIA.missing_now
    assert "production-safe discovery not dependent on CAPTCHA/manual search" in INDIA.missing_now
    assert reopen_trigger_satisfied("India") is False


def test_mexico_open_downloads_do_not_fake_live_incremental_source_contract():
    assert MEXICO.trigger_state == "TRIGGER_FALSE"
    assert "official open-data downloads are advertised for procurement records/contracts" in MEXICO.proven_now
    assert "stable official live/incremental opportunity route" in MEXICO.missing_now
    assert "current API/feed pagination and update contract" in MEXICO.missing_now
    assert reopen_trigger_satisfied("Mexico") is False


def test_no_current_narrow_observation_reopens_hold():
    assert set(HOLD_EVIDENCE_OBSERVATIONS) == {"South Korea", "Australia", "India", "Mexico"}
    assert not any(reopen_trigger_satisfied(country) for country in HOLD_EVIDENCE_OBSERVATIONS)
