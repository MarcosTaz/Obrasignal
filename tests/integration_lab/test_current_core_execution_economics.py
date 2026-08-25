import hashlib
from pathlib import Path

from capability_registry import CAPABILITIES


def _git_blob_sha(path: str) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def test_execution_economics_adds_only_research_capabilities_without_promoting_q080():
    assert CAPABILITIES["EVIDENCE"].state == "EXPERIMENT"
    assert CAPABILITIES["BID_ECONOMICS"].state == "RESEARCH"
    assert CAPABILITIES["BANGS"].state == "RESEARCH"
    assert CAPABILITIES["MOBILIZE"].state == "RESEARCH"
    assert CAPABILITIES["BID_ECONOMICS"].kill_switch_required is True
    assert CAPABILITIES["BANGS"].kill_switch_required is True


def test_core_auth_evidence_rollout_and_master_queue_survive_economics_overlay():
    render = Path("render.yaml").read_text(encoding="utf-8")
    assert "OBRASIGNAL_JWT_ISSUER" in render
    assert "OBRASIGNAL_JWKS_URL" not in render
    assert "key: OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1" in render
    assert "key: OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1" in render
    assert render.count('value: "false"') >= 2

    # Exact current-main queue blob: #240 is PREBUILD and must not mutate queue truth.
    assert _git_blob_sha("master_execution_queue.py") == "1bb6fc147c8a25caf4c27971cce5c00675ebe1c8"
