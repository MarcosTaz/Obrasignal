from italy_anac_pvl import ANAC_PVL_AVVISI, ANAC_HEADERS


def test_anac_pvl_contract_is_public_json_and_credential_free():
    assert ANAC_PVL_AVVISI == "https://pubblicitalegale.anticorruzione.it/api/v0/avvisi"
    assert ANAC_HEADERS["Accept"] == "application/json"
    assert "Authorization" not in ANAC_HEADERS
