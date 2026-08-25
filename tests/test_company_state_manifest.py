import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_machine_readable_integration_manifest_has_required_contract():
    data = json.loads((ROOT / "COMPANY_STATE_INTEGRATION_MANIFEST.json").read_text(encoding="utf-8"))
    required = {
        "CELL", "MODULE", "BRANCH", "PR", "HEAD", "OWNS", "DOES NOT OWN",
        "PUBLIC CONTRACTS PROVIDED", "PUBLIC CONTRACTS CONSUMED", "OPTIONAL DEPENDENCIES",
        "HARD DEPENDENCIES", "CANONICAL FILES TOUCHED", "MIGRATIONS", "FEATURE FLAGS",
        "RUNTIME REGISTRATION", "AUTH/TENANT IMPACT", "PERSISTENCE", "LIVE EXTERNAL DEPENDENCIES",
        "TEST STATUS", "LIVE STATUS", "PRODUCTION STATUS", "CONFLICT RISKS", "KNOWN OVERLAPS",
        "SUPERSEDES", "SUPERSEDED BY", "REQUIRED MERGE ORDER", "ROLLBACK", "SAFE INTEGRATION PROCEDURE",
    }
    assert required <= data.keys()
    assert data["PR"] == 223
    assert data["RUNTIME REGISTRATION"] == "NONE"
    assert data["CANONICAL FILES TOUCHED"] == []
    assert "Q080" in " ".join(data["REQUIRED MERGE ORDER"])


def test_docs_keep_q090_queued_and_no_merge_boundary_explicit():
    text = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in (
        "docs/COMPANY_STATE_V1.md", "docs/COMPANY_STATE_HANDOFFS.md", "COMPANY_STATE_INTEGRATION_MANIFEST.json"
    ))
    assert "QUEUED" in text
    assert "No automatic merge" in text or "Do not merge automatically" in text
    assert "company-state.v1" in text
