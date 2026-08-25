import pytest

from uruguay_arce_pac import ARCEPACConfig, ARCEPACConnector


def test_arce_pac_rejects_source_country_and_family_identity_drift():
    for config, match in (
        (ARCEPACConfig(source="OTHER"), "source identity"),
        (ARCEPACConfig(country="OTHER"), "country identity"),
        (ARCEPACConfig(works_family_code=5), "family code 6"),
    ):
        with pytest.raises(RuntimeError, match=match):
            ARCEPACConnector(config)


def test_arce_pac_rejects_unbounded_execution_config():
    for config, match in (
        (ARCEPACConfig(page_size=0), "page_size"),
        (ARCEPACConfig(page_size=101), "page_size"),
        (ARCEPACConfig(max_pages=0), "max_pages"),
        (ARCEPACConfig(max_pages=51), "max_pages"),
        (ARCEPACConfig(timeout=0), "timeout"),
        (ARCEPACConfig(timeout=121), "timeout"),
    ):
        with pytest.raises(RuntimeError, match=match):
            ARCEPACConnector(config)
