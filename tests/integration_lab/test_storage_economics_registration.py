from pathlib import Path

from storage_contract import KNOWN_TABLE_OWNERS, declared_persistent_tables


def test_security_http_boundary_and_serialized_schema_init_coexist():
    source = Path('cors_app.py').read_text(encoding='utf-8')
    assert 'run_serialized_schema_init(init_db, _app.DB)' in source
    assert 'X-Content-Type-Options' in source
    assert 'X-Frame-Options' in source
    assert '_API_JSON_WRITE_MAX_BYTES' in source
    assert '_redact_operability_payload' in source


def test_company_state_persistence_is_registered_with_storage_owner_contract():
    source = Path('company_state_store.py').read_text(encoding='utf-8')
    declared = declared_persistent_tables(source)
    assert declared
    assert declared <= set(KNOWN_TABLE_OWNERS), (
        'persistent Company State tables must be registered before this combined '
        f'candidate is integration-ready: {sorted(declared - set(KNOWN_TABLE_OWNERS))}'
    )
