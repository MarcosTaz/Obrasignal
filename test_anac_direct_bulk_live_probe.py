"""TEMPORARY ANAC direct-bulk probe. Delete before merge."""
from __future__ import annotations

import io
import json
import struct
import zlib

import requests

BASE = "https://dati.anticorruzione.it/opendata/download/dataset"
DELTA_URLS = [f"{BASE}/cig/filesystem/2026{m:02d}01-cig_csv.zip" for m in range(8, 3, -1)]
FULL_URLS = [
    f"{BASE}/cig-2025/filesystem/cig_csv_2025_12.zip",
    f"{BASE}/cig-2025/filesystem/cig_csv_2025_11.zip",
]


def _range(session, url, end=4_194_303):
    return session.get(url, headers={"Range": f"bytes=0-{end}", "User-Agent": "ObraSignal ANAC forensic probe/1.0"}, timeout=60, allow_redirects=True)


def _zip_prefix_text(blob: bytes, limit=250_000):
    # Parse a single local-file header and stream-decompress enough CSV text.
    if len(blob) < 30 or blob[:4] != b"PK\x03\x04":
        return "", {}
    sig, ver, flags, method, mtime, mdate, crc, csize, usize, nlen, xlen = struct.unpack("<IHHHHHIIIHH", blob[:30])
    name = blob[30:30+nlen].decode("utf-8", "replace")
    start = 30 + nlen + xlen
    raw = blob[start:]
    if method == 0:
        data = raw[:limit]
    elif method == 8:
        dec = zlib.decompressobj(-15)
        data = dec.decompress(raw, limit)
    else:
        return "", {"name": name, "method": method, "flags": flags}
    return data.decode("utf-8-sig", "replace"), {"name": name, "method": method, "flags": flags}


def test_anac_direct_bulk_contract_live():
    s = requests.Session()
    evidence = {"delta": [], "full": []}
    chosen = None
    for kind, urls in (("delta", DELTA_URLS), ("full", FULL_URLS)):
        for url in urls:
            r = _range(s, url)
            item = {
                "url": url, "status": r.status_code, "content_type": r.headers.get("content-type"),
                "content_length": r.headers.get("content-length"), "content_range": r.headers.get("content-range"),
                "accept_ranges": r.headers.get("accept-ranges"), "received": len(r.content),
            }
            if r.status_code in {200, 206} and r.content[:4] == b"PK\x03\x04":
                text, zipmeta = _zip_prefix_text(r.content)
                lines = [line for line in text.splitlines() if line.strip()][:8]
                item["zip"] = zipmeta
                item["csv_prefix"] = lines
                if kind == "delta" and chosen is None:
                    chosen = item
            evidence[kind].append(item)
    evidence["chosen_delta"] = chosen
    raise AssertionError("ANAC_DIRECT_BULK_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:180000])
