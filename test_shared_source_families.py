import pytest

from shared_source_families import (
    FAMILIES,
    SharedSourceFamily,
    assert_shared_family_health,
    audit_shared_families,
    family_for_source,
    members_for_standard,
)
from source_registry import SOURCES


def test_current_shared_family_registry_is_healthy():
    assert audit_shared_families() == ()
    assert assert_shared_family_health() is True


def test_canonical_family_registry_is_immutable():
    with pytest.raises(TypeError):
        FAMILIES["NEW"] = SharedSourceFamily("NEW", "x", "x", (), "x")


def test_ocds_standard_is_backed_by_multiple_shared_transport_families():
    members = set(members_for_standard("OCDS"))
    assert {"PY_DNCP", "ZA_ETENDERS", "UK_PROCUREMENT", "EC_SERCOP"} <= members
    assert len({family.family_id for family in FAMILIES.values() if family.standard == "OCDS"}) == 3


def test_eforms_family_covers_ted_and_publisher_native_xml_exports():
    assert family_for_source("TED").family_id == "TED_SEARCH"
    assert family_for_source("SERVICE_BUND_DE").family_id == "EFORMS_XML"
    assert family_for_source("EE_RHR").family_id == "EFORMS_XML"


def test_generic_adapter_cannot_drift_to_unregistered_family_member():
    registry = {name: dict(meta) for name, meta in SOURCES.items()}
    registry["FAKE_OCDS"] = {
        "official": True,
        "adapter": "OCDSAPIConnector",
        "capabilities": ("incremental_sync",),
    }
    violations = audit_shared_families(registry)
    assert "FAKE_OCDS:adapter_family_mismatch:OCDSAPIConnector:none" in violations


def test_family_member_missing_incremental_capability_fails_closed():
    registry = {name: dict(meta) for name, meta in SOURCES.items()}
    registry["ZA_ETENDERS"]["capabilities"] = ("search",)
    assert "ZA_ETENDERS:missing_incremental_sync_capability" in audit_shared_families(registry)


def test_source_may_not_belong_to_multiple_families():
    families = dict(FAMILIES)
    original = families["OCDS_OPAQUE_CURSOR"]
    families["OCDS_OPAQUE_CURSOR"] = SharedSourceFamily(
        family_id=original.family_id,
        standard=original.standard,
        transport=original.transport,
        members=original.members + ("ZA_ETENDERS",),
        invariant=original.invariant,
        generic_module=original.generic_module,
    )
    violations = audit_shared_families(families=families)
    assert any(v.startswith("ZA_ETENDERS:multiple_families:") for v in violations)
