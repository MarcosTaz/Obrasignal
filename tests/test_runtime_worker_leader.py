import importlib
import os
from pathlib import Path
import subprocess
import sys


def test_runtime_leader_is_process_exclusive(tmp_path, monkeypatch):
    monkeypatch.setenv("OBRASIGNAL_RUNTIME_LOCK_DIR", str(tmp_path))
    import runtime_leader
    runtime_leader = importlib.reload(runtime_leader)

    assert runtime_leader.acquire_runtime_leader() is True
    assert runtime_leader.acquire_runtime_leader() is True

    env = dict(os.environ)
    env["OBRASIGNAL_RUNTIME_LOCK_DIR"] = str(tmp_path)
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runtime_leader; print('leader' if runtime_leader.acquire_runtime_leader() else 'follower')",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert probe.stdout.strip() == "follower"


def test_production_uses_spare_http_capacity_and_one_background_leader():
    root = Path(__file__).resolve().parents[1]
    render = (root / "render.yaml").read_text(encoding="utf-8")
    entrypoint = (root / "cors_app.py").read_text(encoding="utf-8")

    assert "--workers 2" in render
    assert "from runtime_leader import acquire_runtime_leader, serialized_startup" in entrypoint
    assert "with serialized_startup():" in entrypoint
    assert "if acquire_runtime_leader():" in entrypoint
    leader_block = entrypoint.split("if acquire_runtime_leader():", 1)[1]
    assert "start_background_worker()" in leader_block
    assert "start_push_scheduler()" in leader_block
