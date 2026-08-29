from normalization_provenance import normalization_semantic_version
from source_registry import SOURCES


def test_enabled_tender_sources_have_normalization_semantic_identity():
    """Current source-specific projection semantics must remain reconstructable."""
    uncovered = []
    for source, contract in sorted(SOURCES.items()):
        if contract.get("status") not in {"active", "ready"}:
            continue
        if not contract.get("adapter"):
            continue
        if "TENDER" not in set(contract.get("signal_types") or ()):
            continue
        if not normalization_semantic_version(source):
            uncovered.append(source)

    assert uncovered == [], (
        "NORMALIZATION_PROVENANCE_REGISTRY_GAP: active/ready TENDER sources with "
        "concrete adapters lack durable source-specific normalization semantic "
        f"identity: {', '.join(uncovered)}"
    )
