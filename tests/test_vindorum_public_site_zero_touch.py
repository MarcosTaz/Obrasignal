from pathlib import Path


SITE = Path("vertical_apps/industrial_claims/public_site/index.html")


def test_public_site_is_vindorum_zero_touch():
    text = SITE.read_text(encoding="utf-8")
    assert "VINDORUM" in text
    assert 'data-zero-touch="true"' in text
    assert "No meeting required" in text
    assert "Free Exposure Check" in text
    assert "Recovery Scan" in text


def test_public_site_does_not_fake_secure_intake_or_live_checkout():
    text = SITE.read_text(encoding="utf-8")
    assert '<input type="file"' not in text.lower()
    assert 'data-release-gate="production-controls-pending"' in text
    assert "not live yet" in text.lower()
    assert "disabled" in text


def test_public_triage_preserves_truth_boundary():
    text = SITE.read_text(encoding="utf-8")
    assert "not a recoverability or legal-entitlement conclusion" in text
    assert "score<=3" in text
    assert "score<=6" in text
