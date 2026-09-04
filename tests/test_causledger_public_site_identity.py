from __future__ import annotations

from pathlib import Path


SITE = Path("vertical_apps/industrial_claims/public_site/index.html")


def _html() -> str:
    return SITE.read_text(encoding="utf-8")


def test_public_site_uses_only_canonical_certactum_identity():
    html = _html()
    assert "Certactum" in html
    assert "certactum.com" in html
    assert "marcos@certactum.com" in html
    assert "CausLedger" not in html
    assert "causledger.com" not in html.lower()
    assert "ChangeClaim" not in html
    assert "Supplier-side customer-caused cost &amp; margin recovery" in html


def test_public_site_remains_non_indexed_until_production_controls_release_gate_is_closed():
    html = _html()
    assert '<meta name="robots" content="noindex,nofollow">' in html
    assert 'data-release-gate="production-controls-pending"' in html


def test_public_site_cannot_collect_confidential_documents_before_authenticated_intake_is_public():
    html = _html().lower()
    assert 'type="file"' not in html
    assert "<form" not in html
    assert "authenticated evidence workflow" in html
    assert "controlled intake" in html


def test_public_site_preserves_evidence_first_commercial_truth():
    html = _html().lower()
    assert "every conclusion remains tied to its underlying evidence" in html
    assert "no claim / needs review" in html
    assert "what still requires review" in html
    assert "what the available evidence does not support" in html
