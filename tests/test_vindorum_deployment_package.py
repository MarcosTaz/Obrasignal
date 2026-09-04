import json
from pathlib import Path

ROOT = Path("vertical_apps/industrial_claims/public_site")


def test_static_deployment_package_is_complete_and_non_indexed_until_release():
    assert (ROOT / "index.html").is_file()
    assert (ROOT / "vercel.json").is_file()
    assert (ROOT / "robots.txt").read_text(encoding="utf-8") == "User-agent: *\nDisallow: /\n"
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex,nofollow">' in html
    assert 'data-release-gate="production-controls-pending"' in html


def test_static_triage_form_cannot_post_or_upload_confidential_files():
    html = (ROOT / "index.html").read_text(encoding="utf-8").lower()
    assert '<form id="triage">' in html
    assert 'type="file"' not in html
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    headers = {x["key"].lower(): x["value"] for x in config["headers"][0]["headers"]}
    assert "form-action 'none'" in headers["content-security-policy"]
    assert "frame-ancestors 'none'" in headers["content-security-policy"]


def test_deployment_contract_is_vindorum_isolated():
    contract = (ROOT / "DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "VINDORUM" in contract
    assert "new Vercel project dedicated to VINDORUM" in contract
    assert "Do not copy environment variables from another project" in contract
    assert "No production secrets are required" in contract


def test_public_surface_has_no_other_project_identity():
    html = (ROOT / "index.html").read_text(encoding="utf-8").lower()
    for forbidden in ("certactum", "varactum", "contractcredit", "causledger"):
        assert forbidden not in html
