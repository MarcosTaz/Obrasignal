"""Temporary forensic probe for Latvia IUB daily JSON bulk shape; delete after contract freeze."""
from datetime import date, timedelta

import requests

ROOT = "https://open.iub.gov.lv/data/notice"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObraSignal procurement research connector/0.1 (+official open-data validation)",
}


def _summary(value, depth=0):
    if depth >= 2:
        if isinstance(value, (dict, list)):
            return {"type": type(value).__name__, "length": len(value)}
        return value
    if isinstance(value, dict):
        return {key: _summary(val, depth + 1) for key, val in list(value.items())[:40]}
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "first": _summary(value[0], depth + 1) if value else None,
        }
    text = str(value) if value is not None else None
    return text[:300] if isinstance(text, str) else text


def _url(day):
    return f"{ROOT}/{day:%Y/%m/%d-%m-%Y}.json"


def test_lv_iub_current_daily_json_contract_live():
    # Probe the most recent available daily file; weekend/holiday publication
    # gaps must not be mistaken for a source outage during this one-time shape check.
    today = date(2026, 8, 24)
    selected = None
    response = None
    attempts = []
    for offset in range(1, 8):
        day = today - timedelta(days=offset)
        url = _url(day)
        result = requests.get(url, headers=HEADERS, timeout=30)
        attempts.append((url, result.status_code, len(result.content)))
        if result.status_code == 200 and result.content.strip():
            selected = day
            response = result
            break
    assert response is not None, attempts
    payload = response.json()

    if isinstance(payload, list):
        records = [row for row in payload if isinstance(row, dict)]
        root_shape = "list"
        root_keys = []
    elif isinstance(payload, dict):
        root_shape = "dict"
        root_keys = sorted(payload.keys())
        records = []
        for key in ("data", "items", "notices", "records", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                records = [row for row in value if isinstance(row, dict)]
                break
        if not records and payload:
            records = [payload]
    else:
        raise AssertionError({"payload_type": type(payload).__name__, "attempts": attempts})

    first = records[0] if records else {}
    diagnostics = {
        "selected_day": selected.isoformat() if selected else None,
        "url": response.url,
        "status": response.status_code,
        "bytes": len(response.content),
        "content_type": response.headers.get("content-type"),
        "root_shape": root_shape,
        "root_keys": root_keys,
        "record_count": len(records),
        "first_keys": sorted(first.keys()) if isinstance(first, dict) else [],
        "first_summary": _summary(first),
        "attempts": attempts,
    }
    raise AssertionError(diagnostics)
