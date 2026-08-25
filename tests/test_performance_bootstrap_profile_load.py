import pytest

import account_onboarding
import funnel_integration


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _BootstrapConnection:
    def __init__(self, rows):
        self._rows = rows
        self.closed = False

    def execute(self, _sql, _params=()):
        return _Rows(self._rows)

    def close(self):
        self.closed = True


def _evaluation():
    return {
        "lot_score": 80,
        "match": True,
        "lot_id": "lot-1",
        "geography": {"score": 5, "reason": "match"},
        "decision": "QUALIFIED",
        "reason": "synthetic",
        "profile_score": 80,
        "commercial": {},
        "economic_fit": {},
        "capability": {},
        "capability_evidence": {},
        "cpv_evidence": {},
        "hard_capability_blockers": [],
        "explanation": {},
    }


def _patch_bootstrap_domain_work(monkeypatch, profile_loader):
    monkeypatch.setattr(account_onboarding, "ensure_lifecycle_table", lambda _conn: None)
    monkeypatch.setattr(account_onboarding, "_emit_bootstrap_events", lambda _conn, _account_id: 0)
    monkeypatch.setattr(funnel_integration, "load_profile", profile_loader)
    monkeypatch.setattr(account_onboarding, "load_profile", profile_loader)
    monkeypatch.setattr(funnel_integration, "evaluate_row", lambda _item, profile: _evaluation())
    monkeypatch.setattr(funnel_integration, "record_decision", lambda *_args, **_kwargs: None)


def test_bootstrap_loads_one_profile_for_bounded_classification_pass(monkeypatch):
    row_count = 100
    conn = _BootstrapConnection(
        [{"source": "BENCH", "external_id": f"bench-{index:03d}"} for index in range(row_count)]
    )
    profile_calls = []

    def counted_profile(account_id):
        profile_calls.append(account_id)
        return {"account_id": account_id}

    monkeypatch.setattr(account_onboarding, "db", lambda: conn)
    _patch_bootstrap_domain_work(monkeypatch, counted_profile)

    evaluated = account_onboarding.bootstrap_account("tenant-a", limit=row_count)

    assert evaluated == row_count
    assert conn.closed is True
    assert profile_calls == ["tenant-a"], f"profile_load_count={len(profile_calls)}"


def test_each_bootstrap_invocation_reloads_its_own_tenant_profile(monkeypatch):
    connections = [
        _BootstrapConnection([{"source": "BENCH", "external_id": "a"}]),
        _BootstrapConnection([{"source": "BENCH", "external_id": "b"}]),
    ]
    profile_calls = []

    def counted_profile(account_id):
        profile_calls.append(account_id)
        return {"account_id": account_id}

    monkeypatch.setattr(account_onboarding, "db", lambda: connections.pop(0))
    _patch_bootstrap_domain_work(monkeypatch, counted_profile)

    assert account_onboarding.bootstrap_account("tenant-a", limit=1) == 1
    assert account_onboarding.bootstrap_account("tenant-b", limit=1) == 1
    assert profile_calls == ["tenant-a", "tenant-b"]


def test_explicit_profile_snapshot_rejects_cross_tenant_reuse(monkeypatch):
    monkeypatch.setattr(
        funnel_integration,
        "evaluate_row",
        lambda *_args, **_kwargs: pytest.fail("evaluation must not run with cross-tenant profile"),
    )
    monkeypatch.setattr(
        funnel_integration,
        "record_decision",
        lambda *_args, **_kwargs: pytest.fail("persistence must not run with cross-tenant profile"),
    )

    with pytest.raises(ValueError, match="profile account does not match"):
        funnel_integration.persist_and_classify(
            object(),
            {"source": "BENCH", "external_id": "cross-tenant"},
            False,
            account_id="tenant-a",
            profile={"account_id": "tenant-b"},
        )
