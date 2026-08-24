"""TEMPORARY live probe for Estonia RHR open-data XML. Delete before merge."""
from datetime import datetime, timezone
import json
from xml.etree.ElementTree import XMLPullParser

import requests


BASE = "https://riigihanked.riik.ee/rhr/api/public/v1/opendata"
HEADERS = {"User-Agent": "ObraSignal RHR live validation/1.0", "Accept": "application/xml,text/xml,*/*"}


def _local(tag):
    return str(tag).rsplit("}", 1)[-1]


def _bounded_xml_probe(session, url, max_bytes=4 * 1024 * 1024):
    head = session.head(url, headers=HEADERS, timeout=45, allow_redirects=True)
    response = session.get(url, headers={**HEADERS, "Range": f"bytes=0-{max_bytes - 1}"}, timeout=60, stream=True, allow_redirects=True)
    parser = XMLPullParser(events=("start", "end"))
    received = 0
    starts = []
    text_samples = []
    attrs = []
    parse_error = None
    try:
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            remaining = max_bytes - received
            if remaining <= 0:
                break
            chunk = chunk[:remaining]
            received += len(chunk)
            parser.feed(chunk)
            for event, elem in parser.read_events():
                local = _local(elem.tag)
                if event == "start" and len(starts) < 120:
                    starts.append(local)
                    if elem.attrib and len(attrs) < 30:
                        attrs.append({"tag": local, "attrs": dict(list(elem.attrib.items())[:8])})
                elif event == "end" and elem.text and len(text_samples) < 80:
                    text = " ".join(elem.text.split())
                    if text and len(text) <= 240:
                        text_samples.append({"tag": local, "text": text})
                if len(starts) >= 120 and len(text_samples) >= 80:
                    break
            if received >= max_bytes or (len(starts) >= 120 and len(text_samples) >= 80):
                break
    except Exception as exc:
        parse_error = repr(exc)
    finally:
        response.close()
    return {
        "head": {
            "status": head.status_code,
            "final_url": head.url,
            "content_type": head.headers.get("content-type"),
            "content_length": head.headers.get("content-length"),
            "last_modified": head.headers.get("last-modified"),
            "etag": head.headers.get("etag"),
            "accept_ranges": head.headers.get("accept-ranges"),
        },
        "get": {
            "status": response.status_code,
            "final_url": response.url,
            "content_type": response.headers.get("content-type"),
            "content_range": response.headers.get("content-range"),
            "received": received,
        },
        "starts": starts,
        "attrs": attrs,
        "text_samples": text_samples,
        "parse_error": parse_error,
    }


def test_estonia_rhr_monthly_open_data_live():
    session = requests.Session()
    evidence = {"at": datetime.now(timezone.utc).isoformat()}
    for year, month in ((2026, 8), (2026, 7)):
        key = f"{year}-{month:02d}"
        evidence[key] = {}
        for surface in ("notice", "notice_award"):
            url = f"{BASE}/{surface}/{year}/month/{month}/xml"
            evidence[key][surface] = _bounded_xml_probe(session, url)

    raise AssertionError("EE_RHR_EVIDENCE " + json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:50000])
