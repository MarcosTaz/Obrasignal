from pathlib import Path

from factory_cloud.adapters import AdapterRegistry
from factory_cloud.orchestrator import PersistentFactoryOrchestrator
from factory_cloud.state_store import StateStore


def _app(app_id, base, **signals):
    return {
        "app_id": app_id,
        "name": app_id,
        "kind": "application",
        "mission": "test",
        "development_state": "READY",
        "source_truth": {"provider": "github", "repository": "owner/repo", "canonical_branch": "main", "canonical_head": "a" * 40, "verified": True},
        "execution_source": {"provider": "github", "repository": "owner/repo", "branch": f"work/{app_id}", "head": "b" * 40, "verified": True},
        "execution_adapter": {"kind": "test", "configured": True, "allowlisted_tasks": ["task"], "capabilities": ["READ_REPOSITORY", "RUN_TESTS", "UPDATE_BATON"], "repository_mutation_capability": False},
        "task_capabilities": {"task": ["READ_REPOSITORY", "RUN_TESTS", "UPDATE_BATON"]},
        "baton": {"active": "task", "next": [], "wait": []},
        "activation": {"enabled": True, "mode": "repository_safe_execution", "priority": base},
        "portfolio_priority": signals,
    }


def test_pilot_blocker_can_outrank_higher_legacy_priority(tmp_path: Path):
    registry = {
        "applications": [
            _app("legacy-high", 100),
            _app("pilot-critical", 1, pilot_blocker=10),
        ]
    }
    orchestrator = PersistentFactoryOrchestrator(registry, StateStore(tmp_path / "state.sqlite3"), AdapterRegistry())
    assert orchestrator.choose_next().app_id == "pilot-critical"


def test_safety_can_outrank_pilot_and_commercial(tmp_path: Path):
    registry = {
        "applications": [
            _app("commercial", 100, pilot_blocker=100, commercial_leverage=100),
            _app("safety", 1, safety_severity=11),
        ]
    }
    orchestrator = PersistentFactoryOrchestrator(registry, StateStore(tmp_path / "state.sqlite3"), AdapterRegistry())
    assert orchestrator.choose_next().app_id == "safety"


def test_activation_code_is_d_only():
    from factory_cloud.control_plane import ACTIVATION_CODE
    assert ACTIVATION_CODE == "D"
