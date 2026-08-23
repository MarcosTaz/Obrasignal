from source_registry import (
    SOURCES,
    active_sources,
    production_gate_reasons,
    production_ready_sources,
    stale_after_minutes_for,
    wave_sources,
)


def test_verified_active_sources_are_official():
    active = active_sources()
    assert active
    assert all(meta["official"] for meta in active.values())


def test_research_source_is_not_marked_active():
    assert SOURCES["SERVICE_BUND_DE"]["status"] == "research"
    assert "SERVICE_BUND_DE" not in active_sources()


def test_active_sources_have_access_metadata():
    for meta in active_sources().values():
        assert meta["kind"]
        assert meta["access"]
        assert meta["country"]
        assert meta["source_id"]
        assert meta["stale_after_minutes"] > 0


def test_wave_1_contains_only_machine_verified_green_sources():
    wave_1 = wave_sources(1)
    assert len(wave_1) == 15
    assert all(meta["official"] for meta in wave_1.values())
    assert all(meta["machine_access"] == "VERIFIED" for meta in wave_1.values())
    assert all(meta["legal_reuse"] == "GREEN" for meta in wave_1.values())
    assert all(meta["status"] == "planned" for meta in wave_1.values())


def test_germany_does_not_pass_production_gate_until_legal_closure():
    reasons = production_gate_reasons("SERVICE_BUND_DE")
    assert "commercial_reuse_not_green" in reasons
    assert "runtime_not_enabled" in reasons
    assert "SERVICE_BUND_DE" not in production_ready_sources()


def test_planned_wave_source_does_not_become_runtime_active_by_registry_entry_alone():
    reasons = production_gate_reasons("EC_SERCOP")
    assert reasons == ("runtime_not_enabled",)
    assert "EC_SERCOP" not in production_ready_sources()


def test_registered_source_freshness_is_source_specific():
    assert stale_after_minutes_for("TED") == 60
    assert stale_after_minutes_for("LV_IUB") == 4320
    assert stale_after_minutes_for("EE_RHR") == 64800
    assert stale_after_minutes_for("UNKNOWN_SOURCE", default=17) == 17
