"""Official national procurement sources used alongside TED.

Each connector returns the same normalized shape consumed by app.sync_once().
Connectors are isolated so one source outage cannot stop the whole sync.
"""
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import requests


BOAMP_URL = "https://www.boamp.fr/api/explore/v2.1/catalog/datasets/boamp/records"
BOAMP_DAYS = int(os.getenv("BOAMP_DAYS", "30"))
BOAMP_LIMIT = int(os.getenv("BOAMP_LIMIT", "100"))

# PLACSP publishes an official Atom feed for machine-readable reuse. The Spanish
# government specification documents this feed and its CODICE XML mappings.
PLACSP_FEED_URL = "https://contrataciondelestado.es/feeds/portaldetransparencia/licitaciones.atom"
PLACSP_DAYS = int(os.getenv("PLACSP_DAYS", "30"))
PLACSP_MAX_PAGES = int(os.getenv("PLACSP_MAX_PAGES", "20"))


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


def _local_name(tag):
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _first_text(root, names):
    wanted = {str(x).lower() for x in names}
    for node in root.iter():
        if _local_name(node.tag) in wanted and node.text and node.text.strip():
            return node.text.strip()
    return ""


def _all_text(root, names):
    wanted = {str(x).lower() for x in names}
    out = []
    for node in root.iter():
        if _local_name(node.tag) in wanted and node.text and node.text.strip():
            value = node.text.strip()
            if value not in out:
                out.append(value)
    return out


def _iso_date(value):
    if not value:
        return ""
    s = str(value).strip().replace("Z", "+00:00")
    for fn in (
        lambda: datetime.fromisoformat(s).date().isoformat(),
        lambda: datetime.strptime(s[:10], "%Y-%m-%d").date().isoformat(),
        lambda: datetime.strptime(s[:10], "%d-%m-%Y").date().isoformat(),
    ):
        try:
            return fn()
        except Exception:
            pass
    return str(value).strip()


def _iso_datetime(value):
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).astimezone(timezone.utc).isoformat()
    except Exception:
        d = _iso_date(s)
        try:
            return datetime.fromisoformat(d).replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            return None


def fetch_boamp():
    """Fetch recent BOAMP announcements from the French official open-data API."""
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
            "published_at": _iso_datetime(item.get("dateparution")),
            "url": url,
            "market": "EU",
            "place": department,
        })
    return out


def _placsp_entry_to_record(entry):
    # PLACSP's specification uses CODICE namespaces, so local-name matching keeps
    # this parser resilient to namespace-prefix changes without weakening source
    # provenance or inventing fields.
    ext = _first_text(entry, ("ContractFolderID", "ContractFolderId"))
    title = _first_text(entry, ("Name",))
    description = _first_text(entry, ("Description",))
    buyer = _first_text(entry, ("PartyName", "RegistrationName"))
    cpvs = _all_text(entry, ("ItemClassificationCode",))
    value = _first_text(entry, (
        "EstimatedOverallContractAmount",
        "TaxExclusiveAmount",
        "TotalAmount",
    ))
    deadline_date = _first_text(entry, ("EndDate",))
    deadline_time = _first_text(entry, ("EndTime",))
    deadline = deadline_date + ("T" + deadline_time if deadline_date and deadline_time else "")
    publication = _first_text(entry, ("IssueDate", "PublicationDate"))
    updated = _first_text(entry, ("updated", "Updated"))

    # The Atom entry itself normally contains the canonical dossier/notice link.
    url = "https://contrataciondelestado.es/"
    for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
        href = link.attrib.get("href", "").strip()
        rel = link.attrib.get("rel", "alternate").lower()
        if href and rel in ("alternate", "self"):
            url = href
            if rel == "alternate":
                break

    # Some entries expose location as CityName/CountrySubentity. Keep it in the
    # searchable description rather than pretending it is always a province code.
    place_parts = []
    for name in ("CityName", "CountrySubentity", "CountryName"):
        value_part = _first_text(entry, (name,))
        if value_part and value_part not in place_parts:
            place_parts.append(value_part)
    place = " | ".join(place_parts)

    return {
        "source": "PLACSP",
        "external_id": ext,
        "title": title,
        "description": (description + (" | " + place if place else "")).strip(" |"),
        "buyer": buyer,
        "country": "ESP",
        "cpv": " | ".join(cpvs),
        "value": value,
        "deadline": deadline,
        "publication_date": _iso_date(publication or updated),
        "published_at": _iso_datetime(publication or updated),
        "url": url,
        "market": "EU",
        "place": place,
    }


def fetch_placsp():
    """Fetch recent Spanish public-procurement notices from the official Atom feed.

    The feed is paginated with Atom ``next`` links. We walk backward only until
    entries are older than PLACSP_DAYS, bounded by PLACSP_MAX_PAGES.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=PLACSP_DAYS)
    url = PLACSP_FEED_URL
    out = []
    seen_urls = set()

    for _ in range(max(1, PLACSP_MAX_PAGES)):
        if not url or url in seen_urls:
            break
        seen_urls.add(url)
        response = requests.get(url, timeout=45)
        response.raise_for_status()
        root = ET.fromstring(response.content)

        entries = [node for node in root.iter() if _local_name(node.tag) == "entry"]
        oldest = None
        for entry in entries:
            record = _placsp_entry_to_record(entry)
            stamp = record.get("published_at")
            if stamp:
                try:
                    dt = datetime.fromisoformat(stamp)
                    oldest = dt if oldest is None or dt < oldest else oldest
                except Exception:
                    pass
            if not record.get("external_id"):
                continue
            if stamp:
                try:
                    if datetime.fromisoformat(stamp) < cutoff:
                        continue
                except Exception:
                    pass
            out.append(record)

        next_url = ""
        for link in root.findall("{http://www.w3.org/2005/Atom}link"):
            if link.attrib.get("rel", "").lower() == "next":
                next_url = link.attrib.get("href", "").strip()
                break
        if not next_url or (oldest is not None and oldest < cutoff):
            break
        url = next_url

    return out


def fetch_national_sources():
    """Return national-source records; individual source failures are isolated."""
    records = []
    try:
        records.extend(fetch_boamp())
    except Exception as exc:
        print("BOAMP sync error:", exc)
    try:
        records.extend(fetch_placsp())
    except Exception as exc:
        print("PLACSP sync error:", exc)
    return records
