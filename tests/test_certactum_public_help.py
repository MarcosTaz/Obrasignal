from pathlib import Path


HELP = Path("vertical_apps/industrial_claims/public_site/help.html")


def test_customer_help_covers_all_launch_languages_and_core_journey():
    html = HELP.read_text(encoding="utf-8")
    for anchor in ('id="pt"', 'id="en"', 'id="fr"', 'id="es"'):
        assert anchor in html
    assert "marcos@certactum.com" in html
    assert "Proof Pack" in html
    assert "verificação independente" in html
    assert "independent verification" in html
    assert "vérification indépendante" in html
    assert "verificación independiente" in html


def test_help_does_not_invite_confidential_email_intake_or_claim_certification():
    html = HELP.read_text(encoding="utf-8").lower()
    assert "não envie documentação confidencial por email" in html
    assert "do not send confidential documents by email" in html
    assert "certified" not in html
    assert "court accepted" not in html
    assert "guaranteed" not in html
