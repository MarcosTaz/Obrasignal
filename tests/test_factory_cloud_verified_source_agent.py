from pathlib import Path

from factory_cloud.process_adapter import ProcessAdapterConfig
from factory_cloud.verified_source_app_agent import verification_plan


def test_verified_source_agent_allowlist_is_read_only_and_app_specific(tmp_path):
    guarantee = tmp_path / "ventures" / "guaranteerelease"
    guarantee.mkdir(parents=True)
    (guarantee / "engine.test.mjs").write_text("", encoding="utf-8")
    royalty = tmp_path / "factories" / "royaltyrecover"
    royalty.mkdir(parents=True)

    plan = verification_plan("guaranteerelease", "verify:source-tests", root=tmp_path)
    assert plan is not None
    cwd, argv, code = plan
    assert cwd == tmp_path
    assert argv[:2] == ("node", "--test")
    assert argv[2].endswith("ventures/guaranteerelease/engine.test.mjs")
    assert code == "GUARANTEERELEASE_SOURCE_TESTS_GREEN"

    plan = verification_plan("royaltyrecover", "verify:source-tests", root=tmp_path)
    assert plan is not None
    cwd, argv, code = plan
    assert cwd == royalty
    assert argv[-3:] == ("unittest", "-v") or argv[-2:] == ("unittest", "-v")
    assert "unittest" in argv
    assert code == "ROYALTYRECOVER_SOURCE_TESTS_GREEN"

    assert verification_plan("guaranteerelease", "write:source", root=tmp_path) is None
    assert verification_plan("royaltyrecover", "deploy", root=tmp_path) is None
    assert verification_plan("unknown", "verify:source-tests", root=tmp_path) is None


def test_verified_source_adapter_configs_have_no_repository_mutation_capabilities():
    for app_id in ("guaranteerelease", "royaltyrecover"):
        config = ProcessAdapterConfig.load(
            Path(f"factory_cloud/runtime/{app_id}-adapter.json"), expected_app_id=app_id
        )
        assert {item.value for item in config.capabilities} == {"READ_REPOSITORY", "RUN_TESTS", "UPDATE_BATON"}
        assert config.command[-1].endswith("verified_source_app_agent.py")
        assert config.workspace.is_absolute()
