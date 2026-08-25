from pathlib import Path

from source_registry import SOURCES, production_gate_reasons


EXPECTED = {
    "QA_ASHGHAL": ("qa_ashghal_open_etenders", ("TENDER",)),
    "IL_GPA": ("il_gpa_mr_public_procurement", ("TENDER",)),
    "OM_ESNAD": ("om_esnad_public_procurement", ("PROCUREMENT_PLAN",)),
    "AE_MOF_DPP": ("ae_mof_dpp_public_business_opportunities", ("TENDER",)),
}


def test_mena_source_identities_are_single_stable_publishers_and_legally_gated():
    source_ids = []
    for key, (source_id, signal_types) in EXPECTED.items():
        meta = SOURCES[key]
        source_ids.append(meta["source_id"])
        assert meta["source_id"] == source_id
        assert meta["signal_types"] == signal_types
        assert meta["status"] == "planned"
        assert meta["legal_reuse"] == "YELLOW"
        assert meta["machine_access"] == "VERIFIED"
        assert meta["wave"] is None
        assert meta["adapter"]
        assert "commercial_reuse_not_green" in production_gate_reasons(key)
        assert "runtime_not_enabled" in production_gate_reasons(key)
    assert len(source_ids) == len(set(source_ids))


def test_oman_early_signal_is_not_relabelled_as_tender():
    assert SOURCES["OM_ESNAD"]["signal_types"] == ("PROCUREMENT_PLAN",)
    assert "TENDER" not in SOURCES["OM_ESNAD"]["signal_types"]


def test_mena_gated_sources_are_not_wired_into_preload_runtime():
    preload = Path("preload.py").read_text(encoding="utf-8")
    for source_key in EXPECTED:
        assert source_key not in preload


def test_mena_batch_does_not_create_regional_runtime_or_source_family():
    assert not Path("mena_runtime.py").exists()
    assert not Path("international_runtime.py").exists()
    shared = Path("shared_source_families.py").read_text(encoding="utf-8")
    for source_key in EXPECTED:
        assert source_key not in shared
