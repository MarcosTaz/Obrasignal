import pytest

from factories.capacity_commitment import runtime


def test_provider_runtime_requires_durable_db_path(monkeypatch):
    monkeypatch.delenv("CAPACITY_COMMITMENT_DB_PATH", raising=False)
    with pytest.raises(RuntimeError, match="CAPACITY_COMMITMENT_DB_PATH is required"):
        runtime.create_provider_app()


def test_provider_runtime_builds_with_explicit_db_path(tmp_path, monkeypatch):
    seen = {}

    def fake_create_app(repository, tenant_resolver):
        seen["repository"] = repository
        seen["tenant_resolver"] = tenant_resolver
        return "app"

    monkeypatch.setattr(runtime, "create_app", fake_create_app)
    app = runtime.create_provider_app(db_path=str(tmp_path / "capacity.db"))

    assert app == "app"
    assert seen["repository"].db_path.endswith("capacity.db")
    assert seen["tenant_resolver"] is runtime.provider_tenant_resolver
