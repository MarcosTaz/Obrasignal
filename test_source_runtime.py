import json
import sqlite3

from source_health import ensure_source_health, get_source_cursor
from source_metadata import get_source_metadata
from source_runtime import (
    commit_staged_source_syncs,
    discard_staged_source_syncs,
    stage_source_sync,
    staged_source_syncs,
)


def _conn():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    ensure_source_health(conn)
    return conn


def test_stage_does_not_advance_cursor_before_commit():
    conn = _conn()
    discard_staged_source_syncs()
    record = {
        'source': 'CO_SECOP',
        'external_id': 'CO1.REQ.1',
        'taxonomy': 'UNSPSC',
        'category_code': '72141000',
        'signal_type': 'TENDER',
    }
    stage_source_sync('CO_SECOP', [record], 'cursor-1')

    assert len(staged_source_syncs()) == 1
    assert get_source_cursor(conn, 'CO_SECOP') is None
    assert get_source_metadata(conn, 'CO_SECOP', 'CO1.REQ.1') is None

    result = commit_staged_source_syncs(conn)
    assert result == {'sources': 1, 'metadata_records': 1, 'cursors': 1}
    assert get_source_cursor(conn, 'CO_SECOP') == 'cursor-1'
    metadata = get_source_metadata(conn, 'CO_SECOP', 'CO1.REQ.1')
    assert metadata['taxonomy'] == 'UNSPSC'
    assert metadata['category_code'] == '72141000'
    assert metadata['signal_type'] == 'TENDER'
    assert staged_source_syncs() == []


def test_metadata_sidecar_keeps_unknown_future_fields_in_json():
    conn = _conn()
    discard_staged_source_syncs()
    record = {
        'source': 'CO_SECOP',
        'external_id': 'CO1.REQ.2',
        'taxonomy': 'UNSPSC',
        'category_code': '72102900',
        'future_field': 'kept for audit',
    }
    stage_source_sync('CO_SECOP', [record], None)
    result = commit_staged_source_syncs(conn)
    metadata = get_source_metadata(conn, 'CO_SECOP', 'CO1.REQ.2')
    assert result['cursors'] == 0
    assert json.loads(metadata['metadata_json']) == {'future_field': 'kept for audit'}


def test_discard_leaves_database_unchanged():
    conn = _conn()
    discard_staged_source_syncs()
    stage_source_sync(
        'CO_SECOP',
        [{'source': 'CO_SECOP', 'external_id': 'CO1.REQ.3', 'taxonomy': 'UNSPSC'}],
        'cursor-lost',
    )
    discard_staged_source_syncs()
    assert commit_staged_source_syncs(conn) == {'sources': 0, 'metadata_records': 0, 'cursors': 0}
    assert get_source_cursor(conn, 'CO_SECOP') is None
    assert get_source_metadata(conn, 'CO_SECOP', 'CO1.REQ.3') is None


def test_staging_same_source_replaces_previous_uncommitted_observation():
    conn = _conn()
    discard_staged_source_syncs()
    stage_source_sync('CO_SECOP', [{'source': 'CO_SECOP', 'external_id': 'old'}], 'cursor-old')
    stage_source_sync('CO_SECOP', [{'source': 'CO_SECOP', 'external_id': 'new'}], 'cursor-new')
    result = commit_staged_source_syncs(conn)
    assert result['sources'] == 1
    assert get_source_cursor(conn, 'CO_SECOP') == 'cursor-new'
    assert get_source_metadata(conn, 'CO_SECOP', 'old') is None
    assert get_source_metadata(conn, 'CO_SECOP', 'new') is not None
