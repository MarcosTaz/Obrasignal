from __future__ import annotations

from pathlib import Path


SITE = Path("vertical_apps/industrial_claims/public_site/index.html")


def _html() -> str:
    return SITE.read_text(encoding="utf-8")


def test_public_site_uses_only_canonical_causledger_identity():
    html = _html()
    assert "CausLedger" in html
    assert "causledger.com" in html
    assert "marcos@causledger.com" in html
    assert "ChangeClaim" not in html
    assert "Supplier-side customer-caused cost &amp; margin recovery" in html


def test_public_site_remains_non_indexed_until_domain_and_mailbox_release_gate_is_closed():
    html = _html()
    assert '<meta name="robots" content="noindex,nofollow">' in html
    assert 'data-release-gate="domain-and-mailbox-pending"' in html
    assert "Activation gate:" in html
    assert "SPF, DKIM and DMARC" in html


def test_public_site_cannot_collect_confidential_documents_in_preview_state():
    html = _html().lower()
    assert 'type="file"' not in html
    assert "<form" not in html
    assert "does not accept document uploads or confidential case submissions" in html
    assert "do not send confidential evidence" in html


def test_public_site_preserves_fail_closed_commercial_truth():
    html = _html().lower()
    assert "cost is not automatically money owed" in html
    assert "no claim / needs review" in html
    assert "does not guarantee liability, entitlement, payment or recovery" in html
    assert "no automatic claim" in html
