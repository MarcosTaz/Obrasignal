from zambia_zppa import (
    SOURCE,
    ZM_ZPPA_DATA_URL,
    ZM_ZPPA_LICENSE,
    ZM_ZPPA_OFFICIAL_SOURCE,
    ZM_ZPPA_PUBLICATION_POLICY,
    build_zm_connector,
)


def test_zambia_source_contract_is_explicit_and_bounded():
    connector = build_zm_connector()
    assert SOURCE == "ZM_ZPPA"
    assert ZM_ZPPA_OFFICIAL_SOURCE.startswith("https://www.zppa.org.zm/")
    assert "publication/3/download" in ZM_ZPPA_DATA_URL
    assert ZM_ZPPA_LICENSE == "https://creativecommons.org/licenses/by/4.0/"
    assert ZM_ZPPA_PUBLICATION_POLICY.startswith("https://www.zppa.org.zm/")
    assert connector.config.max_compressed_bytes == 32 * 1024 * 1024
    assert connector.config.max_records == 250_000
