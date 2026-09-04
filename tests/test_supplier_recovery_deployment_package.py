import json
from pathlib import Path


ROOT = Path("vertical_apps/industrial_claims/public_site")


def test_static_deployment_package_is_complete_and_non_indexed():
    assert (ROOT / "index.html").is_file()
    assert (ROOT / "vercel.json").is_file()
    assert (ROOT / "robots.txt").read_text(encoding="utf-8") == "User-agent: *\nDisallow: /\n"
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex,nofollow">' in html
    assert 'data-release-gate="production-controls-pending"' in html


def test_vercel_config_is_secret_free_static_and_fail_closed_for_forms_and_frames():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["cleanUrls"] is True
    headers = config["headers"][0]["headers"]
    by_key = {item["key"].lower(): item["value"] for item in headers}
    assert by_key["x-content-type-options"] == "nosniff"
    assert by_key["x-frame-options"] == "DENY"
    assert "form-action 'none'" in by_key["content-security-policy"]
    assert "frame-ancestors 'none'" in by_key["content-security-policy"]
    assert "object-src 'none'" in by_key["content-security-policy"]
    raw = (ROOT / "vercel.json").read_text(encoding="utf-8").lower()
    assert "token" not in raw
    assert "password" not in raw
    assert "database_url" not in raw


def test_deployment_contract_forbids_cross_project_runtime_reuse():
    contract = (ROOT / "DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "Create a new Vercel project dedicated to Supplier Recovery" in contract
    assert "Do not attach any Certactum, Varactum, ContractCredit or other product domain/project/runtime" in contract
    assert "Do not copy environment variables from another project" in contract
    assert "No production secrets are required" in contract
    assert "generated `*.vercel.app` hostname" in contract


def test_rendered_static_surface_has_no_cross_project_identity_or_confidential_intake():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    lowered = html.lower()
    for forbidden in ("certactum", "varactum", "contractcredit", "causledger"):
        assert forbidden not in lowered
    assert "<form" not in lowered
    assert 'type="file"' not in lowered
    assert "upload your documents" not in lowered
    assert "do not email confidential contracts" in lowered
