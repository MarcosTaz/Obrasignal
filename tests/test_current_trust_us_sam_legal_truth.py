"""Latest-trust failing-before for US SAM source-registry legal truth.

Repository evidence issue #520 / Factory #518 currently classifies the exact
Contract Opportunities slice as LEGAL_AMBER until source-scoped commercial
reuse/derivative permission is explicitly captured. Sources retains legal
policy/evidence ownership; this is only the executable fail-closed shape.
"""
from source_registry import SOURCES, production_gate_reasons


def test_us_sam_legal_unknown_or_amber_cannot_be_advertised_as_green():
    sam = SOURCES["US_SAM"]
    assert sam["legal_reuse"] != "GREEN", (
        "SOURCE_REGISTRY_LEGAL_TRUTH_OVERCLAIM: US_SAM is registered legal_reuse=GREEN "
        "while repository evidence #520/#518 remains LEGAL_AMBER pending exact "
        "source-scoped commercial reuse/derivative permission"
    )
    assert "commercial_reuse_not_green" in production_gate_reasons("US_SAM")
