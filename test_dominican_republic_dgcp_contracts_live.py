"""Explicit live contract probe for Dominican Republic DGCP adjudicated contracts."""
import os

import pytest
import requests

from dominican_republic_dgcp import DGCP_API_ROOT


pytestmark = pytest.mark.skipif(
    os.getenv("OBRASIGNAL_LIVE_DGCP") != "1",
    reason="live DGCP probe is explicit opt-in only",
)


def _envelope_rows(path, **params):
    response = requests.get(
        f"{DGCP_API_ROOT}{path}",
        params=params,
        headers={
            "Accept": "application/json",
            "User-Agent": "ObraSignal DGCP contracts live contract probe/1.0",
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
    return rows


def _ocds_detail(ocid):
    response = requests.get(
        f"{DGCP_API_ROOT}/ocds/releases",
        params={"ocid": ocid},
        headers={
            "Accept": "application/json",
            "User-Agent": "ObraSignal DGCP contract OCDS linkage probe/1.0",
        },
        timeout=45,
    )
    response.raise_for_status()
    detail = response.json()
    assert isinstance(detail, dict)
    if isinstance(detail.get("payload"), dict):
        detail = detail["payload"]
        if isinstance(detail.get("content"), dict):
            detail = detail["content"]
    return detail


def test_live_dgcp_contracts_process_and_ocds_lifecycle_link():
    rows = _envelope_rows("/contratos", page=1, limit=25)
    assert rows, "DGCP contracts unexpectedly returned no rows"
    contract = next(
        (
            row
            for row in rows
            if isinstance(row, dict)
            and row.get("codigo_contrato")
            and row.get("codigo_proceso")
        ),
        None,
    )
    assert contract is not None
    print("DGCP_CONTRACT_FIELDS=" + ",".join(sorted(map(str, contract.keys()))))

    processes = _envelope_rows(
        "/procesos",
        page=1,
        limit=10,
        proceso=contract["codigo_proceso"],
    )
    assert processes, "DGCP contract process link unexpectedly returned no process"
    process = next((row for row in processes if isinstance(row, dict)), None)
    assert process is not None
    print("DGCP_CONTRACT_PROCESS_FIELDS=" + ",".join(sorted(map(str, process.keys()))))

    ocid = f"ocds-6550wx-{contract['codigo_proceso']}"
    detail = _ocds_detail(ocid)
    releases = detail.get("releases") if isinstance(detail, dict) else None
    assert isinstance(releases, list) and releases, "DGCP process OCID returned no releases"
    relevant = [row for row in releases if isinstance(row, dict)]
    assert relevant
    awards = [award for release in relevant for award in (release.get("awards") or []) if isinstance(award, dict)]
    contracts = [item for release in relevant for item in (release.get("contracts") or []) if isinstance(item, dict)]
    print(
        "DGCP_OCDS_LIFECYCLE "
        f"award_count={len(awards)} contract_count={len(contracts)} "
        f"award_fields={','.join(sorted(awards[0])) if awards else ''} "
        f"contract_fields={','.join(sorted(contracts[0])) if contracts else ''}"
    )
    assert awards, "DGCP adjudicated process OCDS package has no awards"
    assert contracts, "DGCP adjudicated process OCDS package has no contracts"
