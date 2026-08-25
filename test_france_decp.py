from datetime import date

import pytest

import france_decp as fr


class Response:
    def __init__(self, payload, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)


def _works(**overrides):
    row = {
        "id": "FR-CONTRACT-1",
        "objet": "Réhabilitation d'un groupe scolaire",
        "codecpv": "45214200-2",
        "procedure": "Appel d'offres ouvert",
        "nature": "Marché",
        "acheteur_nom": "Ville Exemple",
        "acheteur_id": "12345678900011",
        "montant": 1250000,
        "dureemois": 18,
        "datenotification": "2026-08-20",
        "datepublicationdonnees": "2026-08-22",
        "titulaire_denominationsociale_1": "Entreprise Bâtiment",
        "titulaire_typeidentifiant_1": "SIRET",
        "titulaire_id_1": "98765432100012",
        "lieuexecution_nom": "Paris",
        "source": "profil-acheteur",
    }
    row.update(overrides)
    return row


def test_emits_contract_not_tender_and_uses_native_cpv():
    session = Session([Response({"total_count": 1, "results": [_works()]})])
    rows, cursor = fr.fetch_france_decp_contracts(
        watermark="2026-08-20", session=session, today=date(2026, 8, 25)
    )
    assert cursor == "2026-08-22"
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "FR_DECP"
    assert row["signal_type"] == "CONTRACT"
    assert row["external_id"] == "FR-CONTRACT-1"
    assert row["taxonomy"] == "CPV"
    assert row["category_code"].startswith("45")
    assert row["currency"] == "EUR"
    assert "Entreprise Bâtiment" in row["description"]


def test_server_query_is_bounded_to_construction_and_incremental_window():
    session = Session([Response({"total_count": 0, "results": []})])
    rows, cursor = fr.fetch_france_decp_contracts(
        watermark="2026-08-20", session=session, today=date(2026, 8, 25)
    )
    assert rows == []
    assert cursor == "2026-08-20"
    params = session.calls[0][1]["params"]
    assert 'startswith(codecpv, "45")' in params["where"]
    assert "2026-08-18" in params["where"]
    assert params["limit"] <= 100


def test_non_construction_is_rejected_even_if_server_filter_regresses():
    session = Session([Response({"total_count": 1, "results": [_works(codecpv="71300000-1")]})])
    rows, cursor = fr.fetch_france_decp_contracts(
        watermark="2026-08-20", session=session, today=date(2026, 8, 25)
    )
    assert rows == []
    assert cursor == "2026-08-20"


def test_modification_updates_same_contract_identity():
    original = _works(datepublicationdonnees="2026-08-21", montant=1000000)
    modified = _works(
        datepublicationdonnees="2026-08-21",
        booleanmodification=True,
        datepublicationdonneesmodification="2026-08-24",
        montant=1250000,
    )
    session = Session([Response({"total_count": 2, "results": [original, modified]})])
    rows, cursor = fr.fetch_france_decp_contracts(
        watermark="2026-08-20", session=session, today=date(2026, 8, 25)
    )
    assert cursor == "2026-08-24"
    assert len(rows) == 1
    assert rows[0]["external_id"] == "FR-CONTRACT-1"
    assert rows[0]["has_modification"] is True
    assert rows[0]["value"] == "1250000"


def test_missing_identity_or_update_fails_closed():
    session = Session([Response({"total_count": 1, "results": [_works(id="")]})])
    with pytest.raises(RuntimeError, match="missing id/update date"):
        fr.fetch_france_decp_contracts(
            watermark="2026-08-20", session=session, today=date(2026, 8, 25)
        )


def test_untrusted_record_url_is_not_forwarded():
    session = Session([
        Response({"total_count": 1, "results": [_works(url="https://evil.example/payload")]})
    ])
    rows, _ = fr.fetch_france_decp_contracts(
        watermark="2026-08-20", session=session, today=date(2026, 8, 25)
    )
    assert rows[0]["url"] == fr.DECP_HUMAN


def test_schema_error_is_transport_failure_not_empty_success():
    session = Session([Response({"unexpected": []})] * (fr.DECP_RETRIES + 1))
    with pytest.raises(RuntimeError, match="unexpected response schema"):
        fr.fetch_france_decp_contracts(
            watermark="2026-08-20", session=session, today=date(2026, 8, 25)
        )


def test_pagination_cap_fails_closed(monkeypatch):
    monkeypatch.setattr(fr, "DECP_MAX_PAGES", 1)
    monkeypatch.setattr(fr, "DECP_PAGE_SIZE", 1)
    session = Session([Response({"total_count": 2, "results": [_works()]})])
    with pytest.raises(RuntimeError, match="pagination cap reached"):
        fr.fetch_france_decp_contracts(
            watermark="2026-08-20", session=session, today=date(2026, 8, 25)
        )
