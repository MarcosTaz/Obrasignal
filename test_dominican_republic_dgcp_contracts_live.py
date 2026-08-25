"""Explicit live contract probe for Dominican Republic DGCP adjudicated contracts."""
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


def test_live_dgcp_contracts_and_process_link_contract():
    rows = _get("/contratos", page=1, limit=25)
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
    # Field names are structural evidence; values are deliberately not logged.
    print("DGCP_CONTRACT_FIELDS=" + ",".join(sorted(map(str, contract.keys()))))

    processes = _get(
        "/procesos",
        page=1,
        limit=10,
        proceso=contract["codigo_proceso"],
    )
    assert processes, "DGCP contract process link unexpectedly returned no process"
    process = next((row for row in processes if isinstance(row, dict)), None)
    assert process is not None
    print("DGCP_CONTRACT_PROCESS_FIELDS=" + ",".join(sorted(map(str, process.keys()))))
