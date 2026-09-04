from pathlib import Path


HELP = Path("vertical_apps/industrial_claims/public_site/help.html")


def test_customer_help_covers_all_launch_languages_and_zero_touch_journey():
    html = HELP.read_text(encoding="utf-8")
    for anchor in ('id="pt"', 'id="en"', 'id="fr"', 'id="es"'):
        assert anchor in html
    assert "VINDORUM" in html
    assert "Free Exposure Check" in html
    assert "VINDORUM Recovery Dossier" in html
    assert "Self-service by default" in html
    assert "marcos@" not in html.lower()


def test_help_blocks_confidential_email_intake_and_cross_project_identity():
    html = HELP.read_text(encoding="utf-8").lower()
    assert "não envie contratos" in html
    assert "do not send contracts" in html
    assert "n'envoyez pas de contrats" in html
    assert "no envíe contratos" in html
    for forbidden in ("certactum", "causledger", "supplier recovery", "varactum", "obrasignal.com"):
        assert forbidden not in html


def test_help_preserves_truth_boundaries():
    html = HELP.read_text(encoding="utf-8").lower()
    assert "does not establish recoverability or money owed" in html
    assert "blocks confidential documents" in html
    for forbidden in ("certified", "court accepted", "guaranteed recovery"):
        assert forbidden not in html
