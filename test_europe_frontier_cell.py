from pathlib import Path

from market_scope_registry import MARKET_SCOPE
from source_registry import SOURCES


FRONTIER_NEW = {
    "Turkey",
    "Serbia",
    "Georgia",
    "Albania",
    "North Macedonia",
    "Moldova",
    "Bosnia and Herzegovina",
    "Montenegro",
}


def test_cell_does_not_silently_inflate_canonical_market_scope():
    assert FRONTIER_NEW.isdisjoint(MARKET_SCOPE)


def test_cell_does_not_fake_unverified_source_registry_entries():
    countries = {meta["country"] for meta in SOURCES.values()}
    assert {"TUR", "SRB", "GEO", "ALB", "MKD", "MDA", "BIH", "MNE"}.isdisjoint(countries)


def test_switzerland_is_existing_ready_connector_not_new_cell_work():
    assert MARKET_SCOPE["Switzerland"].status == "BUILD"
    assert SOURCES["CH_SIMAP"]["status"] == "ready"
    assert SOURCES["CH_SIMAP"]["adapter"] == "SIMAPConnector"


def test_ukraine_remains_canonical_hold():
    assert MARKET_SCOPE["Ukraine"].status == "HOLD"
    assert "risco de guerra" in MARKET_SCOPE["Ukraine"].reopen_condition


def test_cell_evidence_documents_exist():
    for path in (
        "EUROPE_FRONTIER_CELL_RESEARCH.md",
        "TURKEY_EKAP_EVIDENCE.md",
        "SERBIA_PROCUREMENT_EVIDENCE.md",
        "UKRAINE_PROZORRO_EVIDENCE.md",
        "BALKANS_SOURCE_GATES.md",
    ):
        assert Path(path).is_file()
