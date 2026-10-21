"""Explicit live contract probe for Dominican Republic DGCP PACC early signals."""
import os

import pytest
import requests

from dominican_republic_dgcp import DGCP_API_ROOT


pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_DGCP") != "1",
    reason="live DGCP probe is explicit opt-in only",
)


def _get(path, **params):
    response = requests.get(
        f"{DGCP_API_ROOT}{path}",
        params=params,
        headers={
            "Accept": "application/json",
            "User-Agent": "ObraSignal DGCP PACC live contract probe/1.0",
        },
        timeout=45,
    )
    response.raise_for_status()
    envelope = response.json()
    assert isinstance(envelope, dict)
    assert envelope.get("hasError") is False
    assert envelope.get("code") == 200
    payload = envelope.get("payload")
    assert isinstance(payload, dict)
    rows = payload.get("content")
    assert isinstance(rows, list)
    return payload, rows


def test_live_dgcp_pacc_acquisitions_and_articles_contract():
    payload, rows = _get("/pacc/adquisiciones", page=1, limit=10)
    assert rows, "DGCP PACC acquisitions unexpectedly returned no rows"
    print("DGCP_PACC_PAYLOAD_FIELDS=" + ",".join(sorted(map(str, payload.keys()))))
    acquisition = next(
        (row for row in rows if isinstance(row, dict) and row.get("id_adquisicion")),
        None,
    )
    assert acquisition is not None
    assert str(acquisition.get("objeto_adquisicion") or "").strip(), "PACC acquisition has no controlled object type"
    print("DGCP_PACC_FIELDS=" + ",".join(sorted(map(str, acquisition.keys()))))

    _, articles = _get(
        "/pacc/articulos",
        page=1,
        limit=50,
        adquisicion_id=acquisition["id_adquisicion"],
    )
    assert articles, "DGCP PACC acquisition unexpectedly returned no articles"
    article = next((row for row in articles if isinstance(row, dict)), None)
    assert article is not None
    assert any(article.get(key) for key in ("familia_unspsc", "clase_unspsc", "subclase_unspsc"))
    print("DGCP_PACC_ARTICLE_FIELDS=" + ",".join(sorted(map(str, article.keys()))))
