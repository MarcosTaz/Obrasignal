"""Quality controls for multi-source procurement ingestion.

The same procurement procedure can appear in TED and a national portal.
This module provides deterministic, conservative deduplication helpers without
silently deleting records that cannot be matched with high confidence.
"""
import re
import unicodedata


def _norm(value):
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def canonical_key(record):
    """Return a stable key when the source provides a trustworthy identifier."""
    source = _norm(record.get("source"))
    external_id = _norm(record.get("external_id"))
    if source and external_id:
        return f"source:{source}:{external_id}"
    return None


def opportunity_key(record):
    """Backward-compatible identity helper for callers and tests."""
    return canonical_key(record)


def similarity_key(record):
    """Build a conservative cross-source fingerprint.

    We intentionally require several independent fields. A title alone is not
    sufficient because recurring framework/procurement notices often share titles.
    """
    country = _norm(record.get("country"))
    buyer = _norm(record.get("buyer"))
    title = _norm(record.get("title"))
    cpv = _norm(record.get("cpv"))
    deadline = _norm(str(record.get("deadline", ""))[:10])
    value = _norm(record.get("value"))
    if not country or not title or not buyer:
        return None
    title = " ".join(title.split()[:18])
    buyer = " ".join(buyer.split()[:12])
    return "|".join((country, buyer, title, cpv, deadline, value))


def dedupe_records(records):
    """Deduplicate exact source IDs while preserving cross-source records."""
    seen = set()
    out = []
    for record in records or []:
        key = canonical_key(record)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(record)
    return out


def source_summary(records):
    """Return deterministic source/country counts for observability."""
    summary = {}
    for record in records or []:
        source = record.get("source") or "UNKNOWN"
        country = record.get("country") or "---"
        summary.setdefault(source, {"country": country, "count": 0})
        summary[source]["count"] += 1
    return summary
