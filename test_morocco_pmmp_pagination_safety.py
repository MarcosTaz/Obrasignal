import pytest

from morocco_pmmp import (
    MoroccoPMMPSourceError,
    fetch_current_construction_consultations,
)


PAGE = """
<html><body><h2>Résultats de la recherche</h2><table>
<tr><td>AOO Appel d'offres ouvert Travaux 22/08/2026</td><td>63/2026 - ... Objet : TRAVAUX DE CONSTRUCTION ... Acheteur public : BUYER A</td><td>RABAT</td><td>08/10/2026 12:00</td></tr>
</table>{next_link}</body></html>
"""


class _Response:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class _StaticSession:
    def __init__(self, html):
        self.html = html
        self.urls = []

    def get(self, url, timeout, headers):
        self.urls.append(url)
        return _Response(self.html)


def test_page_cap_fails_closed_instead_of_returning_partial_results():
    session = _StaticSession(PAGE.format(next_link='<a href="?page=2" title="Page suivante">next</a>'))
    with pytest.raises(MoroccoPMMPSourceError, match="exceeds max_pages=1"):
        fetch_current_construction_consultations(session=session, max_pages=1)


def test_webforms_postback_is_not_emulated_or_silently_accepted():
    session = _StaticSession(PAGE.format(next_link='<a href="javascript:__doPostBack(\'pager\',\'2\')" title="Page suivante">next</a>'))
    with pytest.raises(MoroccoPMMPSourceError, match="WebForms pagination is unsupported"):
        fetch_current_construction_consultations(session=session, max_pages=2)


def test_next_page_cannot_escape_official_https_host():
    session = _StaticSession(PAGE.format(next_link='<a href="https://example.com/page/2" title="Page suivante">next</a>'))
    with pytest.raises(MoroccoPMMPSourceError, match="escaped the official HTTPS host"):
        fetch_current_construction_consultations(session=session, max_pages=2)


def test_invalid_page_bounds_are_rejected_before_network_access():
    session = _StaticSession(PAGE.format(next_link=""))
    for invalid in (0, 21, True, 1.5):
        with pytest.raises(ValueError):
            fetch_current_construction_consultations(session=session, max_pages=invalid)
    assert session.urls == []
