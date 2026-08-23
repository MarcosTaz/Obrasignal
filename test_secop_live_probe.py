"""Temporary forensic live probe; remove after one successful CI run."""
import requests


def test_official_secop_construction_query_live():
    response = requests.get(
        "https://www.datos.gov.co/resource/p6dx-8zbt.json",
        params={
            "$select": "id_del_proceso,tipo_de_contrato,estado_de_apertura_del_proceso,fecha_de_ultima_publicaci,urlproceso",
            "$where": "estado_de_apertura_del_proceso = 'Abierto' AND tipo_de_contrato = 'Obra'",
            "$order": "fecha_de_ultima_publicaci DESC,id_del_proceso DESC",
            "$limit": "5",
        },
        timeout=30,
    )
    response.raise_for_status()
    rows = response.json()
    assert isinstance(rows, list)
    assert rows, "official SECOP query returned no open works"
    for row in rows:
        assert row["tipo_de_contrato"] == "Obra"
        assert row["estado_de_apertura_del_proceso"] == "Abierto"
        assert row.get("id_del_proceso")
        assert row.get("fecha_de_ultima_publicaci")
