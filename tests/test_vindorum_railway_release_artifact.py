from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(".")
PUBLIC = Path("vertical_apps/industrial_claims/public_site")
MAIN_SHA = "f330eda1ff6572d201d32befd6de731ee3241346"


def test_container_is_static_vindorum_only_and_does_not_start_application_backend():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM caddy:2.11.4-alpine")
    assert "COPY vertical_apps/industrial_claims/public_site/ /srv/" in dockerfile
    assert "COPY ." not in dockerfile
    assert "python" not in dockerfile.lower()
    assert "gunicorn" not in dockerfile.lower()
    assert "flask" not in dockerfile.lower()
    assert "npm" not in dockerfile.lower()
    assert "EXPOSE 8080" in dockerfile


def test_build_context_is_deny_by_default_and_only_allows_public_release_material():
    rules = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert rules[0].strip() == "*"
    allowed = {line.strip() for line in rules if line.startswith("!")}
    assert allowed == {
        "!Dockerfile",
        "!Caddyfile",
        "!vertical_apps/",
        "!vertical_apps/industrial_claims/",
        "!vertical_apps/industrial_claims/public_site/",
        "!vertical_apps/industrial_claims/public_site/**",
    }
    assert not any(".env" in line.lower() for line in allowed)
    assert not any("factory" in line.lower() for line in allowed)


def test_runtime_headers_preserve_public_metadata_security_boundary():
    caddy = (ROOT / "Caddyfile").read_text(encoding="utf-8")
    required = (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Content-Security-Policy",
        "Cross-Origin-Opener-Policy",
        "Cross-Origin-Resource-Policy",
        "form-action 'none'",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "script-src 'none'",
        "connect-src 'none'",
    )
    for token in required:
        assert token in caddy
    assert "header @release Cache-Control \"no-store\"" in caddy


def test_release_manifest_binds_public_artifact_to_exact_green_main_without_claiming_paid_launch():
    release = json.loads((PUBLIC / "release.json").read_text(encoding="utf-8"))
    assert release["product"] == "VINDORUM"
    assert release["release_kind"] == "PUBLIC_METADATA_SITE"
    assert release["application_main_sha"] == MAIN_SHA
    assert release["paid_scan_backend_ready"] is False
    assert release["commercial_launch_ready"] is False
    assert release["confidential_evidence_intake_enabled"] is False
    assert "does not mean paid scanning" in release["truth_boundary"]


def test_public_release_keeps_confidential_and_paid_actions_disabled():
    index = (PUBLIC / "index.html").read_text(encoding="utf-8").lower()
    assert "vindorum" in index
    assert "data-release-gate=\"production-controls-pending\"" in index
    assert "<form" not in index
    assert "type=\"file\"" not in index
    assert "causledger" not in index
    assert "certactum" not in index
    assert "obrasignal" not in index
