from datetime import datetime, timedelta, timezone
import sqlite3
import tempfile

import pytest

from company_state import (
    CompanyFact,
    CompanyState,
    CompanyStateError,
    FactCategory,
    KnowledgeState,
    Provenance,
    ProvenanceBasis,
)
from company_state_store import CompanyStateService, save_company_state

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def make_conn(path):
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def manual_crew(value):
    return {
        "category": "AVAILABILITY",
        "code": "crew.available_count",
        "knowledge": "FACT",
        "value": value,
        "unit": "workers",
    }


def trusted_verified_crew(value):
    return CompanyFact(
        FactCategory.AVAILABILITY,
        "crew.available_count",
        KnowledgeState.FACT,
        value,
        Provenance(
            ProvenanceBasis.VERIFIED,
            source_ref="trusted-provider",
            evidence_ref="ev_verified_crew",
            observed_at=NOW,
            verified_at=NOW,
        ),
        unit="workers",
    )


def test_manual_update_supersedes_previous_manual_value_without_false_conflict():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        first = service.patch("tenant-a", {"facts": [manual_crew(4)]}, clock=NOW)
        second = service.patch("tenant-a", {"facts": [manual_crew(5)]}, clock=NOW + timedelta(minutes=1))
        assert second.single_current_value("crew.available_count") == 5
        assert len(second.facts) == 2
        newest = next(fact for fact in second.facts if fact.value == 5)
        assert newest.supersedes == (first.facts[0].fact_id,)
        assert not second.to_dict()["conflicts"]


def test_revoking_latest_manual_value_does_not_resurrect_older_manual_value():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        service.patch("tenant-a", {"facts": [manual_crew(4)]}, clock=NOW)
        current = service.patch("tenant-a", {"facts": [manual_crew(5)]}, clock=NOW + timedelta(minutes=1))
        newest = next(fact for fact in current.facts if fact.value == 5)
        revoked = service.patch(
            "tenant-a",
            {"revoke_fact_ids": [newest.fact_id]},
            clock=NOW + timedelta(minutes=2),
        )
        assert revoked.single_current_value("crew.available_count") is None
        assert not [fact for fact in revoked.facts if fact.code == "crew.available_count"]
        assert service.get_version("tenant-a", 1).single_current_value("crew.available_count") == 4
        assert service.get_version("tenant-a", 2).single_current_value("crew.available_count") == 5


def test_manual_boundary_cannot_revoke_trusted_verified_fact():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        conn = make_conn(fh.name)
        verified = trusted_verified_crew(7)
        save_company_state(conn, CompanyState("tenant-a", NOW, (verified,)), expected_version=0, clock=NOW)
        conn.close()
        service = CompanyStateService(lambda: make_conn(fh.name))
        with pytest.raises(CompanyStateError, match="only voluntary manual facts"):
            service.patch("tenant-a", {"revoke_fact_ids": [verified.fact_id]}, clock=NOW + timedelta(minutes=1))
        assert service.get("tenant-a").single_current_value("crew.available_count") == 7


def test_manual_boundary_cannot_choose_supersession_target():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        raw = manual_crew(4)
        raw["supersedes"] = ["cf_" + "a" * 24]
        with pytest.raises(CompanyStateError, match="cannot select supersession"):
            service.patch("tenant-a", {"facts": [raw]}, clock=NOW)


def test_manual_fact_does_not_silently_supersede_trusted_fact():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        conn = make_conn(fh.name)
        verified = trusted_verified_crew(7)
        save_company_state(conn, CompanyState("tenant-a", NOW, (verified,)), expected_version=0, clock=NOW)
        conn.close()
        service = CompanyStateService(lambda: make_conn(fh.name))
        mixed = service.patch("tenant-a", {"facts": [manual_crew(5)]}, clock=NOW + timedelta(minutes=1))
        assert mixed.single_current_value("crew.available_count") is None
        manual = next(fact for fact in mixed.facts if fact.provenance.source_ref == "manual")
        assert mixed.to_dict()["conflicts"] == [{
            "category": "AVAILABILITY",
            "code": "crew.available_count",
            "scope": None,
            "fact_ids": sorted([verified.fact_id, manual.fact_id]),
        }]


def test_duplicate_semantic_keys_in_one_manual_patch_are_rejected_not_last_write_wins():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        with pytest.raises(CompanyStateError, match="duplicate semantic keys"):
            service.patch("tenant-a", {"facts": [manual_crew(4), manual_crew(5)]}, clock=NOW)
        assert service.get("tenant-a") is None


def test_same_manual_fact_same_clock_remains_idempotent_after_supersession_hardening():
    with tempfile.NamedTemporaryFile(suffix=".db") as fh:
        service = CompanyStateService(lambda: make_conn(fh.name))
        first = service.patch("tenant-a", {"facts": [manual_crew(4)]}, clock=NOW)
        second = service.patch("tenant-a", {"facts": [manual_crew(4)]}, clock=NOW)
        assert first.fingerprint == second.fingerprint
        assert first.state_version == second.state_version == 1
