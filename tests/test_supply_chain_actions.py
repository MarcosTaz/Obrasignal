import re
from pathlib import Path

import supply_chain_actions


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _raw_uses():
    specs = []
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.search(r"\buses:\s*([^\s#]+)", line)
            if match:
                specs.append((path.name, match.group(1)))
    return specs


def test_inventory_covers_every_workflow_action_occurrence():
    observed = supply_chain_actions.inventory()["actions"]
    normalized = [(item["workflow"], f"{item['action']}@{item['reference']}") for item in observed]
    assert normalized == _raw_uses()


def test_supply_chain_resolution_uses_only_commit_pinned_actions_and_bounded_write_authority():
    report = supply_chain_actions.inventory()
    owned = [item for item in report["actions"] if item["workflow"] == "supply-chain-resolution.yml"]
    assert owned
    assert all(item["pin_type"] == "COMMIT_PINNED" for item in owned)
    workflow = next(item for item in report["workflows"] if item["workflow"] == "supply-chain-resolution.yml")
    assert workflow["secret_names"] == []
    # Workflow default remains least-privilege read. The one owner job explicitly
    # elevates to contents:write only to materialize the already-reproduced lock.
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["job_permissions"] == {"npm-resolution": {"contents": "write"}}
    assert workflow["job_write_permissions"] == {"npm-resolution": ["contents:write"]}
    assert all(item["write_permissions"] == ["contents:write"] for item in owned)

    text = (WORKFLOWS / "supply-chain-resolution.yml").read_text(encoding="utf-8")
    assert "github.head_ref == 'supply-chain/lock-integrity-v1-20260825'" in text
    assert "test \"$GITHUB_HEAD_REF\" = 'supply-chain/lock-integrity-v1-20260825'" in text
    assert "test \"$GITHUB_BASE_REF\" = 'main'" in text
    assert "repos/${GITHUB_REPOSITORY}/contents/mobile/package-lock.json" in text
    assert "--input /tmp/lock-put.json" in text
    assert "secrets." not in text


def test_remaining_secret_bearing_mutable_actions_are_visible_as_critical_debt():
    report = supply_chain_actions.inventory()
    debt = [
        item for item in report["actions"]
        if item["secret_names"] and item["pin_type"] != "COMMIT_PINNED"
    ]
    assert debt
    assert all(item["criticality"] == "CRITICAL" for item in debt)
    workflows = {item["workflow"] for item in debt}
    # Authenticated E2E is deliberately no longer debt on this integration tree:
    # Auth #289's immutable checkout is composed with Release #414's read-only job.
    assert "authenticated-e2e.yml" not in workflows
    assert {"auth-verifier-live.yml", "eas-preview.yml", "eas-production.yml", "mobile-release-preflight.yml", "web-preview.yml"} <= workflows

    authenticated = [
        item for item in report["actions"]
        if item["workflow"] == "authenticated-e2e.yml" and item["secret_names"]
    ]
    assert authenticated
    assert all(item["pin_type"] == "COMMIT_PINNED" for item in authenticated)


def test_248_proven_pin_candidates_are_reused_as_evidence_not_workflow_authority():
    report = supply_chain_actions.inventory()
    eas = [
        item for item in report["actions"]
        if item["workflow"] in {"eas-preview.yml", "eas-production.yml"}
    ]
    assert eas
    assert all(item["proven_248_pin_candidate"] for item in eas)
    # Canonical/candidate workflows remain mutable until separately composed;
    # knowing a candidate SHA is not the same as having that SHA in this workflow.
    assert all(item["pin_type"] == "MUTABLE_TAG" for item in eas)


def test_implicit_workflow_permissions_fail_closed_as_unknown_default():
    report = supply_chain_actions.inventory()
    workflows = {item["workflow"]: item for item in report["workflows"]}
    for name in ("canadabuys_live.yml", "eas-preview.yml", "eas-production.yml", "quality.yml", "us_sam_live.yml"):
        assert workflows[name]["permissions"] == {"__authority__": "IMPLICIT_DEFAULT"}
        assert workflows[name]["write_permissions"] == ["UNKNOWN_DEFAULT"]


def test_toolchain_drift_is_observable_not_normalized_away():
    workflows = {item["workflow"]: item for item in supply_chain_actions.inventory()["workflows"]}
    assert workflows["quality.yml"]["node_versions"] == ["22.13.1"]
    assert workflows["mobile-release-preflight.yml"]["node_versions"] == ["22.13.1"]
    assert workflows["eas-preview.yml"]["node_versions"] == ["24"]
    assert workflows["eas-production.yml"]["node_versions"] == ["24"]
    assert workflows["eas-preview.yml"]["eas_versions"] == ["latest"]
    assert workflows["eas-production.yml"]["eas_versions"] == ["latest"]
