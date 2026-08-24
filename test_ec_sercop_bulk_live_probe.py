"""Temporary forensic probe for the official SERCOP monthly OCDS JSON bulk export.

Delete after the download contract and package shape are frozen.
"""
from io import BytesIO
import json
import zipfile

import requests

URL = (
    "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/download"
    "?type=json&year=2026&month=08&method=all"
)
HEADERS = {
    "Accept": "application/zip, application/octet-stream, application/json",
    "User-Agent": "ObraSignal procurement connector research/0.1 (+official open-data validation)",
}


def test_sercop_august_2026_bulk_download_contract_live():
    response = requests.get(URL, headers=HEADERS, timeout=90)
    response.raise_for_status()
    payload = response.content
    diagnostics = {
        "status": response.status_code,
        "url": response.url,
        "content_type": response.headers.get("content-type"),
        "content_disposition": response.headers.get("content-disposition"),
        "content_length": len(payload),
        "zip": zipfile.is_zipfile(BytesIO(payload)),
    }
    if diagnostics["zip"]:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            names = archive.namelist()
            diagnostics["entries"] = names[:20]
            diagnostics["entry_count"] = len(names)
            json_names = [name for name in names if name.lower().endswith(".json")]
            diagnostics["json_count"] = len(json_names)
            if json_names:
                with archive.open(json_names[0]) as handle:
                    first = json.load(handle)
                diagnostics["json_root_type"] = type(first).__name__
                diagnostics["json_root_keys"] = sorted(first.keys()) if isinstance(first, dict) else None
                if isinstance(first, dict):
                    diagnostics["package_uri"] = first.get("uri")
                    diagnostics["package_license"] = first.get("license")
                    releases = first.get("releases")
                    diagnostics["release_count"] = len(releases) if isinstance(releases, list) else None
                    diagnostics["first_release_keys"] = sorted(releases[0].keys()) if isinstance(releases, list) and releases and isinstance(releases[0], dict) else None
    raise AssertionError(diagnostics)
