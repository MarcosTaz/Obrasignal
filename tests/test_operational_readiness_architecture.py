from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readiness_policy_does_not_import_legacy_economic_profile_shape():
    source = (ROOT / "opportunity_readiness.py").read_text(encoding="utf-8")
    assert "from economic_fit import" not in source
    assert "evaluate_economic_fit(" not in source


def test_requirements_company_state_integration_uses_public_adapter_not_storage():
    source = (ROOT / "requirements_company_state_adapter.py").read_text(encoding="utf-8")
    assert "from company_state_adapters import requirements_facts" in source
    assert "company_state_store" not in source
    assert "company_profile" not in source


def test_preference_geography_is_filtered_at_company_state_public_seam():
    source = (ROOT / "company_state_adapters.py").read_text(encoding="utf-8")
    assert 'code.startswith("geography.preferred_")' in source
    assert "FactCategory.AVAILABILITY" in source
    assert '"non_current_facts"' in source


def test_integration_does_not_register_readiness_in_production_runtime():
    runtime = (ROOT / "cors_app.py").read_text(encoding="utf-8")
    assert "install_readiness_api" not in runtime
    assert "readiness_api" not in runtime


def test_no_master_queue_or_capability_registry_ownership_in_integration_modules():
    for name in ("requirements_company_state_adapter.py", "readiness_requirements_adapter.py", "opportunity_readiness.py", "readiness_api.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "master_execution_queue" not in source
        assert "capability_registry" not in source
