"""Bounded live probe for DGCP bulk process/contract table exports.

The publisher may return large XLSX files. The probe enforces a hard download
cap and uses only Python's standard library to inspect the workbook header, so
we can validate transport/schema before adding any XLSX runtime dependency.
"""
from io import BytesIO
import os
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import pytest
import requests

from dominican_republic_dgcp import DGCP_API_ROOT


pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_DGCP") != "1",
    reason="live DGCP probe is explicit opt-in only",
)

MAX_PROBE_BYTES = 64 * 1024 * 1024
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _xlsx_headers(blob):
    with ZipFile(BytesIO(blob)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{_NS}si"):
                shared.append("".join(node.text or "" for node in item.iter(f"{_NS}t")))

        sheet_names = sorted(
            name for name in archive.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        assert sheet_names, "DGCP XLSX has no worksheet XML"
        root = ET.fromstring(archive.read(sheet_names[0]))
        row = root.find(f".{_NS}sheetData/{_NS}row")
        assert row is not None, "DGCP XLSX first worksheet has no rows"
        values = []
        for cell in row.findall(f"{_NS}c"):
            cell_type = cell.attrib.get("t")
            if cell_type == "inlineStr":
                values.append("".join(node.text or "" for node in cell.iter(f"{_NS}t")))
                continue
            value = cell.find(f"{_NS}v")
            raw = value.text if value is not None and value.text is not None else ""
            if cell_type == "s" and raw:
                raw = shared[int(raw)]
            values.append(raw)
        return tuple(str(value).strip() for value in values)


def _probe(path):
    with requests.get(
        f"{DGCP_API_ROOT}{path}",
        headers={
            "Accept": "*/*",
            "User-Agent": "ObraSignal DGCP bulk live contract probe/1.0",
        },
        timeout=60,
        stream=True,
    ) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        disposition = response.headers.get("Content-Disposition", "")
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=256 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_PROBE_BYTES:
                raise AssertionError(
                    f"DGCP bulk endpoint {path} exceeds {MAX_PROBE_BYTES} byte live-probe cap"
                )
            chunks.append(chunk)
        blob = b"".join(chunks)
        assert blob.startswith(b"PK"), f"DGCP bulk endpoint {path} is not an XLSX/ZIP stream"
        headers = _xlsx_headers(blob)
        assert headers, f"DGCP bulk endpoint {path} has no workbook headers"
        print(
            f"DGCP_BULK path={path} content_type={content_type!r} "
            f"content_disposition={disposition!r} bytes={len(blob)} "
            f"headers={','.join(headers)}"
        )
        return content_type, disposition, len(blob), headers


def test_live_dgcp_process_and_contract_bulk_transports():
    process_type, process_disposition, process_size, process_headers = _probe("/tablas/procesos")
    contract_type, contract_disposition, contract_size, contract_headers = _probe("/tablas/contratos")
    assert process_type or process_disposition
    assert contract_type or contract_disposition
    assert process_size > 0
    assert contract_size > 0
    assert any("proceso" in value.lower() for value in process_headers)
    assert any("contrato" in value.lower() for value in contract_headers)
