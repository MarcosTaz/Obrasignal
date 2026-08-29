from pathlib import Path


def test_auth_screen_explains_customer_workflow_before_signup():
    source = Path("mobile/components/AuthScreen.tsx").read_text(encoding="utf-8")

    assert "Encontra e filtra concursos de obra" in source
    assert "perfil da tua empresa" in source
    assert "razão do encaixe" in source
    assert "shortlist explicada" in source
    assert "guarda as oportunidades que merecem investigação" in source


def test_auth_copy_does_not_make_unproved_commercial_outcome_claims():
    source = Path("mobile/components/AuthScreen.tsx").read_text(encoding="utf-8").lower()

    forbidden = (
        "ganha mais contratos",
        "aumenta a receita",
        "poupa milhares",
        "garante",
        "mais vendas",
    )
    assert all(claim not in source for claim in forbidden)
