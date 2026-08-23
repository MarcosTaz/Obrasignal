from datetime import datetime, timedelta, timezone

import app
from api import _deadline_state
from company_profile import derive_profile
from opportunity_match_pipeline import evaluate_row


def _profile(activity, interests, min_value, max_value):
    return derive_profile(activity, {
        "activity": activity,
        "contract_interests": interests,
        "countries": ["PRT"],
        "cpv_prefixes": [],
        "keywords": [],
        "min_value": min_value,
        "max_value": max_value,
    })


def _row(title, description, cpv, value, country="PRT", deadline="2099-12-31"):
    return {"title": title, "description": description, "buyer": "Município", "cpv": cpv,
            "value": value, "country": country, "deadline": deadline}


def test_huge_value_mismatch_is_material_and_explained_even_for_formatted_source_value():
    profile = _profile("serralharia e estruturas metálicas", ["fabrico de estruturas metálicas"], 100_000, 500_000)
    result = evaluate_row(_row(
        "Construção de estrutura metálica", "Fabrico e montagem em aço", "45223100", "22 000 000 EUR"
    ), profile)

    assert result["profile_score"] <= 35
    assert result["decision"] == "REJECT"
    assert result["economic_fit"]["status"] == "UNFAVOURABLE"
    assert "valor acima do máximo da empresa" in result["reason"]

    us_formatted = evaluate_row(_row(
        "Construção de estrutura metálica", "Fabrico e montagem em aço", "45223100", "22,000,000 EUR"
    ), profile)
    assert us_formatted["profile_score"] <= 35


def test_specific_activity_interest_and_cpv_beat_generic_works_match_for_each_trade():
    cases = [
        (_profile("serralharia e estruturas metálicas", ["fabrico de estruturas metálicas"], 100_000, 500_000),
         _row("Fabrico de estruturas metálicas", "Serralharia e montagem em aço", "45223100", "300000")),
        (_profile("pintura e acabamentos", ["pintura de edifícios"], 20_000, 250_000),
         _row("Pintura de edifícios", "Pintura interior e acabamentos", "45442100", "120000")),
        (_profile("instalações elétricas", ["quadros elétricos e iluminação"], 50_000, 500_000),
         _row("Instalações elétricas", "Quadros elétricos e iluminação", "45310000", "200000")),
    ]
    generic = _row("Renovação de escola", "Empreitada geral de construção e manutenção", "45214200", "200000")

    for profile, specific in cases:
        specific_result = evaluate_row(specific, profile)
        generic_result = evaluate_row(generic, profile)
        assert specific_result["profile_score"] > generic_result["profile_score"]
        assert specific_result["capability_evidence"]["matched"] is True


def test_outside_country_and_expired_deadline_cannot_present_as_high_or_open():
    profile = _profile("instalações elétricas", ["quadros elétricos e iluminação"], 50_000, 500_000)
    outside = evaluate_row(_row("Instalações elétricas", "Iluminação", "45310000", "200000", country="ESP"), profile)
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    assert outside["profile_score"] <= 35
    assert "país fora da cobertura da empresa" in outside["reason"]
    assert _deadline_state(expired)["state"] == "closed"
    assert _deadline_state(None)["state"] == "unknown"


def test_known_location_outside_declared_regions_is_a_hard_mismatch():
    profile = _profile("pintura e acabamentos", ["pintura de edifícios"], 20_000, 250_000)
    profile["regions"] = ["Porto"]
    row = _row("Pintura de edifícios", "Pintura interior", "45442100", "120000")
    row["locations"] = [{"country": "PRT", "city": "Leiria"}]
    result = evaluate_row(row, profile)

    assert result["profile_score"] <= 35
    assert "região fora da cobertura da empresa" in result["reason"]


def test_missing_procurement_data_is_unknown_and_never_positive_evidence():
    profile = _profile("pintura e acabamentos", ["pintura de edifícios"], 20_000, 250_000)
    result = evaluate_row({"title": None, "description": None, "buyer": None, "cpv": None,
                           "value": None, "country": None, "deadline": None}, profile)

    assert result["profile_score"] < 20
    assert result["economic_fit"]["status"] == "UNKNOWN"
    assert result["capability_evidence"]["matched"] is False
    assert "valor do contrato inexistente ou inválido" in result["reason"]
    assert "capacidade=não foram encontradas capacidades explícitas" in result["reason"]


def test_reprocessing_existing_tender_preserves_first_seen_and_does_not_inflate_new24(monkeypatch, tmp_path):
    db_path = tmp_path / "new24.db"
    monkeypatch.setattr(app, "DB", str(db_path))
    normalized = {
        "source": "TED", "external_id": "REPROCESS-1", "title": "Pintura", "description": "Acabamentos",
        "buyer": "Município", "country": "PRT", "cpv": "45442100", "value": "100000",
        "deadline": "2099-12-31", "publication_date": "2026-01-01", "url": "https://example.test/1",
        "market": "PT", "published_at": "2026-01-01T00:00:00+00:00",
    }
    monkeypatch.setattr(app, "fetch_ted", lambda: [{"id": "raw"}])
    monkeypatch.setattr(app, "normalize_ted", lambda _: dict(normalized))
    monkeypatch.setattr(app, "fetch_base", lambda: [])

    app.sync_once()
    old = "2020-01-01T00:00:00+00:00"
    conn = app.db()
    conn.execute("UPDATE tenders SET first_seen=? WHERE external_id=?", (old, "REPROCESS-1"))
    conn.commit()
    conn.close()

    app.sync_once()
    conn = app.db()
    row = conn.execute("SELECT first_seen FROM tenders WHERE external_id='REPROCESS-1'").fetchone()
    new24 = conn.execute("SELECT COUNT(*) FROM tenders WHERE julianday(first_seen)>=julianday('now','-1 day')").fetchone()[0]
    conn.close()

    assert row["first_seen"] == old
    assert new24 == 0
