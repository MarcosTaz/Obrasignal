"""Official national procurement sources used alongside TED.

Each connector returns the same normalized shape consumed by app.sync_once().
Connectors are deliberately isolated so a source outage cannot stop TED.
"""
import os
from datetime import datetime, timezone, timedelta

import requests


BOAMP_URL = "https://www.boamp.fr/api/explore/v2.1/catalog/datasets/boamp/records"
BOAMP_DAYS = int(os.getenv("BOAMP_DAYS", "30"))
BOAMP_LIMIT = int(os.getenv("BOAMP_LIMIT", "100"))


def _text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        if isinstance(value, dict):
            for key in ("label", "libelle", "name", "value", "code"):
                if value.get(key):
                    return str(value[key])
        return " | ".join(str(x) for x in value if x not in (None, ""))
    return str(value).strip()


def fetch_boamp():
    """Fetch recent BOAMP announcements from the French official open-data API.

    BOAMP exposes the dataset through an OpenDataSoft Explore API. We deliberately
    keep this connector narrow: recent records only, with source provenance kept
    as BOAMP so the app never presents them as TED notices.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=BOAMP_DAYS)).date().isoformat()
    params = {
        "limit": max(1, min(100, BOAMP_LIMIT)),
        "order_by": "dateparution desc",
        "where": f"dateparution >= '{since}'",
    }
    response = requests.get(BOAMP_URL, params=params, timeout=45)
    response.raise_for_status()
    payload = response.json()
    records = payload.get("results", []) if isinstance(payload, dict) else []

    out = []
    for item in records:
        if not isinstance(item, dict):
            continue
        ext = _text(item.get("idweb") or item.get("id"))
        if not ext:
            continue

        title = _text(item.get("objet"))
        buyer = _text(item.get("nomacheteur"))
        department = _text(item.get("code_departement_prestation") or item.get("code_departement"))
        family = _text(item.get("famille_libelle") or item.get("famille"))
        descriptors = _text(item.get("descripteur_libelle"))
        description = " | ".join(x for x in (family, descriptors) if x)
        url = _text(item.get("url_avis")) or "https://www.boamp.fr/"

        out.append({
            "source": "BOAMP",
            "external_id": ext,
            "title": title,
            "description": description,
            "buyer": buyer,
            "country": "FRA",
            "cpv": _text(item.get("dc") or item.get("descripteur_code")),
            "value": _text(item.get("montant") or item.get("montant_ht") or item.get("montant_estime")),
            "deadline": _text(item.get("datelimitereponse")),
            "publication_date": _text(item.get("dateparution")),
            "published_at": None,
            "url": url,
            "market": "EU",
            "place": department,
        })
    return out


def fetch_national_sources():
    """Return national-source records; individual source failures are isolated."""
    records = []
    try:
        records.extend(fetch_boamp())
    except Exception:
        # TED remains the authoritative baseline; a national connector outage
        # must never make the whole synchronization fail.
        pass
    return records
