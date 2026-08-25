from datetime import datetime, timedelta, timezone
import sqlite3
import tempfile
import threading
import pytest

from company_state import CompanyFact, CompanyState, CompanyStateError, FactCategory, KnowledgeState, Provenance, ProvenanceBasis, TenantBoundaryError
from company_state_store import (
    CompanyStateService, StaleCompanyStateWrite, company_state_history,
    company_state_version, current_company_state, ensure_company_state_schema,
    save_company_state,
)

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)
PROV = Provenance(ProvenanceBasis.DECLARED, observed_at=NOW)


def crew(value):
    return CompanyFact(FactCategory.AVAILABILITY, "crew.available_count", KnowledgeState.FACT, value, PROV, unit="workers")


def make_conn(path=":memory:"):
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def test_schema_is_additive_and_repeated_startup_safe():
    conn = make_conn()
    conn.execute("CREATE TABLE unrelated(id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO unrelated(value) VALUES('keep')")
    ensure_company_state_schema(conn)
    ensure_company_state_schema(conn)
    assert conn.execute("SELECT value FROM unrelated").fetchone()[0] == "keep"
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='company_state_snapshots'").fetchone()


def test_first_save_and_read_are_tenant_scoped():
    conn = make_conn()
    saved = save_company_state(conn, CompanyState("a", NOW, (crew(4),)), expected_version=0, clock=NOW)
    assert saved.state_version == 1
    assert current_company_state(conn, "a").fingerprint == saved.fingerprint
    assert current_company_state(conn, "b") is None


def test_consecutive_same_snapshot_is_idempotent():
    conn = make_conn()
    s = CompanyState("a", NOW, (crew(4),))
    first = save_company_state(conn, s, expected_version=0, clock=NOW)
    second = save_company_state(conn, s, expected_version=1, clock=NOW + timedelta(seconds=1))
    assert second.state_version == 1
    assert conn.execute("SELECT COUNT(*) FROM company_state_snapshots WHERE account_id='a'").fetchone()[0] == 1


def test_a_b_a_transition_preserves_history():
    conn = make_conn()
    a = CompanyState("a", NOW, (crew(4),))
    b = CompanyState("a", NOW + timedelta(minutes=1), (crew(5),))
    a2 = CompanyState("a", NOW + timedelta(minutes=2), (crew(4),))
    v1 = save_company_state(conn, a, expected_version=0, clock=NOW)
    v2 = save_company_state(conn, b, expected_version=1, clock=NOW)
    v3 = save_company_state(conn, a2, expected_version=2, clock=NOW)
    assert [v.state_version for v in company_state_history(conn, "a")] == [3, 2, 1]
    assert v1.fingerprint != v3.fingerprint  # as_of is materially different


def test_stale_write_is_rejected_not_overwritten():
    conn = make_conn()
    save_company_state(conn, CompanyState("a", NOW, (crew(4),)), expected_version=0, clock=NOW)
    with pytest.raises(StaleCompanyStateWrite):
        save_company_state(conn, CompanyState("a", NOW + timedelta(minutes=1), (crew(5),)), expected_version=0, clock=NOW)
    assert current_company_state(conn, "a").single_current_value("crew.available_count") == 4


def test_historical_version_read_is_tenant_scoped():
    conn = make_conn()
    save_company_state(conn, CompanyState("a", NOW, (crew(4),)), expected_version=0, clock=NOW)
    save_company_state(conn, CompanyState("b", NOW, (crew(8),)), expected_version=0, clock=NOW)
    assert company_state_version(conn, "a", 1).single_current_value("crew.available_count") == 4
    assert company_state_version(conn, "b", 1).single_current_value("crew.available_count") == 8
    assert company_state_version(conn, "a", 2) is None


def test_service_rejects_client_controlled_tenant_and_state_identity():
    conn = make_conn()
    # shared in-memory connection cannot be reused after close; this test only
    # exercises validation before factory connection use.
    service = CompanyStateService(lambda: make_conn())
    for key in ("account_id", "tenant_id", "fingerprint", "state_version", "contract_version"):
        with pytest.raises(TenantBoundaryError):
            service.patch("a", {key: "b"}, clock=NOW)


def test_patch_missing_is_leave_unchanged_revocation_is_explicit():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        factory = lambda: make_conn(fh.name)
        service = CompanyStateService(factory)
        first = service.patch("a", {"facts": [crew(4).to_dict()]}, clock=NOW)
        unchanged = service.patch("a", {"company_ref": "company-1"}, clock=NOW + timedelta(minutes=1))
        assert unchanged.single_current_value("crew.available_count") == 4
        revoked = service.patch("a", {"revoke_fact_ids": [crew(4).fact_id]}, clock=NOW + timedelta(minutes=2))
        assert revoked.single_current_value("crew.available_count") is None
        assert [s.state_version for s in service.history("a")] == [3, 2, 1]


def test_patch_null_is_not_missing_delete_or_unknown():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        service.patch("a", {"facts": [crew(4).to_dict()]}, clock=NOW)
        for payload in ({"facts": None}, {"revoke_fact_ids": None}, {"as_of": None}, {"expected_version": None}):
            with pytest.raises(CompanyStateError):
                service.patch("a", payload, clock=NOW)
        assert service.get("a").single_current_value("crew.available_count") == 4


def test_tenant_a_cannot_read_update_or_list_b_via_service():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        service.patch("a", {"facts": [crew(4).to_dict()]}, clock=NOW)
        service.patch("b", {"facts": [crew(8).to_dict()]}, clock=NOW)
        assert service.get("a").single_current_value("crew.available_count") == 4
        assert service.get("b").single_current_value("crew.available_count") == 8
        assert all(item.account_id == "a" for item in service.history("a"))
        with pytest.raises(TenantBoundaryError):
            service.patch("a", {"account_id": "b", "facts": [crew(99).to_dict()]}, clock=NOW)
        assert service.get("b").single_current_value("crew.available_count") == 8


def test_idempotency_is_tenant_scoped():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        a = service.patch("a", {"facts": [crew(4).to_dict()]}, clock=NOW)
        b = service.patch("b", {"facts": [crew(4).to_dict()]}, clock=NOW)
        assert a.state_version == b.state_version == 1
        assert a.fingerprint != b.fingerprint


def test_sql_metacharacters_are_inert_tenant_data_or_rejected_by_contract():
    conn = make_conn()
    # tenant pattern rejects SQL-like ids before SQL, and queries are parameterized.
    with pytest.raises(TenantBoundaryError):
        CompanyState("a' OR 1=1 --", NOW, ())
    assert conn.execute("SELECT 1").fetchone()[0] == 1


def test_history_limit_bounded():
    conn = make_conn()
    with pytest.raises(CompanyStateError):
        company_state_history(conn, "a", limit=1000)


def test_corrupt_storage_is_error_not_empty_state():
    conn = make_conn()
    ensure_company_state_schema(conn)
    conn.execute("INSERT INTO company_state_snapshots(account_id,state_version,fingerprint,contract_version,as_of,snapshot_json,created_at) VALUES(?,?,?,?,?,?,?)",
                 ("a",1,"bad","company-state.v1",NOW.isoformat(),"{bad",NOW.isoformat()))
    conn.commit()
    from company_state_store import CompanyStateStorageError
    with pytest.raises(CompanyStateStorageError):
        current_company_state(conn, "a")


def test_invalid_trusted_account_is_denied_not_returned_as_empty():
    conn = make_conn()
    with pytest.raises(TenantBoundaryError):
        current_company_state(conn, "../../tenant")


def test_oversized_fact_array_is_rejected_before_state_build():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        with pytest.raises(CompanyStateError):
            service.patch("a", {"facts": [crew(1).to_dict()] * 257}, clock=NOW)


def test_service_implicitly_binds_write_to_snapshot_it_read(monkeypatch):
    import company_state_store as module
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        first = service.patch("a", {"facts": [crew(4).to_dict()]}, clock=NOW)
        seen = {}
        real = module.save_company_state
        def wrapped(conn, state, *, expected_version=None, clock=None):
            seen["expected"] = expected_version
            return real(conn, state, expected_version=expected_version, clock=clock)
        monkeypatch.setattr(module, "save_company_state", wrapped)
        service.patch("a", {"company_ref": "company-a"}, clock=NOW + timedelta(minutes=1))
        assert seen["expected"] == first.state_version


def test_concurrent_updates_do_not_lose_a_write(monkeypatch):
    import company_state_store as module
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        service.patch("a", {"facts": [crew(4).to_dict()]}, clock=NOW)
        barrier = threading.Barrier(2)
        real = module.save_company_state
        results = []
        errors = []

        def synchronized_save(conn, state, *, expected_version=None, clock=None):
            barrier.wait(timeout=5)
            return real(conn, state, expected_version=expected_version, clock=clock)

        monkeypatch.setattr(module, "save_company_state", synchronized_save)

        def writer(value):
            try:
                results.append(service.patch("a", {"facts": [crew(value).to_dict()]}, clock=NOW + timedelta(minutes=value)))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(5,)), threading.Thread(target=writer, args=(6,))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert all(not thread.is_alive() for thread in threads)
        assert len(results) == 1
        assert len(errors) == 1 and isinstance(errors[0], StaleCompanyStateWrite)
        assert service.get("a").state_version == 2
