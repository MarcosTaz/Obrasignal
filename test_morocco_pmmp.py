import sqlite3

import pytest
import requests

from morocco_pmmp import (
    MoroccoPMMPConnector,
    MoroccoPMMPSourceError,
    PMMPConsultation,
    fetch_current_construction_consultations,
    normalize_consultation,
    parse_consultations_page,
)
from signal_store import get_signal_record, persist_signal_records


PAGE1 = """
<html><body><h2>Résultats de la recherche</h2><table>
<tr><th>Procédure Catégorie Publié le</th><th>Référence Objet Acheteur public</th><th>Lieu</th><th>Date limite</th></tr>
<tr><td>AOO Appel d'offres ouvert Travaux 22/08/2026</td><td>63/2026 - ... Objet : TRAVAUX DE CONSTRUCTION D'UN CENTRE D’ACCUEIL A LA COMMUNE TIGHIRT ... Acheteur public : DIRECTEUR REGIONAL DU MINISTERE DE LA JEUNESSE ET DES SPORTS REGION GUELMIM OUED NOUN</td><td>SIDI IFNI</td><td>08/10/2026 12:00</td></tr>
<tr><td>AOO Appel d'offres ouvert Travaux 19/08/2026</td><td>338/26/ASST - ... Objet : travaux d’assainissement liquide du centre de Talmest ... Acheteur public : SOCIETE REGIONALE MULTISERVICES MARRAKECH - SAFI S.A</td><td>ESSAOUIRA</td><td>05/10/2026 10:00</td></tr>
</table><a href="?page=2"><img alt="Aller à la page suivante"></a></body></html>
"""

PAGE2 = """
<html><body><h2>Résultats de la recherche</h2><table>
<tr><td>AOO Appel d'offres ouvert Travaux 10/08/2026</td><td>04/2026 - ... Objet : TRAVAUX D’AMENAGEMENT AU NIVEAU DU SIEGE DE LA COMMUNE LAAOUAMA ... Acheteur public : Commune LAAOUAMA</td><td>TANGER-ASSILAH</td><td>30/09/2026 11:00</td></tr>
</table></body></html>
"""


def test_parse_official_construction_category_rows():
    rows, next_href = parse_consultations_page(PAGE1)
    assert [r.reference for r in rows] == ["63/2026", "338/26/ASST"]
    assert rows[0].published == "22/08/2026"
    assert rows[0].deadline == "08/10/2026 12:00"
    assert rows[0].location == "SIDI IFNI"
    assert next_href == "?page=2"
    signal = normalize_consultation(rows[0])
    assert signal["source"] == "MA_PMMP"
    assert signal["signal_type"] == "TENDER"
    assert signal["source_reference"] == "63/2026"
    assert signal["external_id"].endswith("::63/2026")
    assert signal["country"] == "MAR"
    assert signal["publication_date"] == "2026-08-22"
    assert signal["deadline"] == "2026-10-08T12:00"


class _Response:
    def __init__(self, text): self.text = text
    def raise_for_status(self): return None


class _Session:
    def __init__(self): self.urls = []
    def get(self, url, timeout, headers):
        self.urls.append(url)
        assert timeout == 7
        return _Response(PAGE2 if "page=2" in url else PAGE1)


def test_pagination_follows_publisher_next_link():
    session = _Session()
    rows = fetch_current_construction_consultations(session=session, timeout=7, max_pages=2)
    assert [r.reference for r in rows] == ["63/2026", "338/26/ASST", "04/2026"]
    assert len(session.urls) == 2
    records = MoroccoPMMPConnector(session=_Session(), timeout=7, max_pages=2).fetch()
    assert len(records) == 3


def test_reference_is_namespaced_by_buyer_to_avoid_cross_buyer_collisions():
    a = PMMPConsultation("63/2026", "Travaux A", "Buyer A", "22/08/2026", "08/10/2026 12:00", "AOO")
    b = PMMPConsultation("63/2026", "Travaux B", "Buyer B", "22/08/2026", "08/10/2026 12:00", "AOO")
    assert normalize_consultation(a)["external_id"] != normalize_consultation(b)["external_id"]
    assert normalize_consultation(a)["source_reference"] == normalize_consultation(b)["source_reference"] == "63/2026"


def test_canonical_signal_store_idempotent_update():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    record = normalize_consultation(parse_consultations_page(PAGE1)[0][0])
    assert persist_signal_records(conn, [record], observed_at="2026-08-25T00:00:00+00:00", expected_source="MA_PMMP") == 1
    updated = dict(record, title=record["title"] + " UPDATED")
    assert persist_signal_records(conn, [updated], observed_at="2026-08-25T01:00:00+00:00", expected_source="MA_PMMP") == 1
    stored = get_signal_record(conn, "MA_PMMP", record["external_id"], "TENDER")
    assert stored["title"].endswith("UPDATED")
    assert stored["first_observed"] == "2026-08-25T00:00:00+00:00"
    assert stored["last_observed"] == "2026-08-25T01:00:00+00:00"


def test_deadline_before_publication_fails_closed():
    row = PMMPConsultation("x/2026", "Travaux", "Buyer", "22/08/2026", "01/08/2026 12:00", "AOO")
    with pytest.raises(MoroccoPMMPSourceError, match="predates"):
        normalize_consultation(row)


class _FailingSession:
    def get(self, *args, **kwargs): raise requests.Timeout("publisher timeout")


def test_transport_failure_is_error_not_zero():
    with pytest.raises(MoroccoPMMPSourceError, match="fetch failed"):
        fetch_current_construction_consultations(session=_FailingSession(), timeout=1, max_pages=1)


def test_changed_contract_is_error_not_zero():
    with pytest.raises(MoroccoPMMPSourceError):
        parse_consultations_page("<html><body>No results</body></html>")
