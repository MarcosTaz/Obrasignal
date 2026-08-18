from source_registry import SOURCES, active_sources


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
