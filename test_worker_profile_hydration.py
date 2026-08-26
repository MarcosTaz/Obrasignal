class _Rows:
    def __init__(self, *, one=None, many=None):
        self._one = one
        self._many = many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._many)


class _Conn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=()):
        normalized = " ".join(sql.lower().split())
        if "from sync_runs" in normalized:
            return _Rows(one={"finished_at": "sync-1"})
        if "from tenders t" in normalized and "where t.last_seen" in normalized:
            assert params == ("sync-1",)
            return _Rows(many=self.rows)
        raise AssertionError(f"unexpected sql: {sql}")


def test_worker_hydrates_profile_once_per_account_and_keeps_all_decisions(monkeypatch):
    import lifecycle_read_model

    accounts = ["account-a", "account-b", "account-c"]
    rows = [
        {"source": "TEST", "external_id": f"row-{index}"}
        for index in range(5)
    ]
    profile_loads = []
    classifications = []

    monkeypatch.setattr(lifecycle_read_model, "_ensure", lambda conn: None)

    def load_profile(account_id):
        profile_loads.append(account_id)
        return {"account_id": account_id, "marker": f"profile:{account_id}"}

    def classify(conn, item, is_new, account_id="default", profile=None):
        assert is_new is True
        assert profile is not None
        assert profile["account_id"] == account_id
        classifications.append((account_id, item["external_id"], profile["marker"]))
        return "REVIEW", "test"

    monkeypatch.setattr(lifecycle_read_model, "load_profile", load_profile)
    monkeypatch.setattr(lifecycle_read_model, "persist_and_classify", classify)

    recorded = lifecycle_read_model.record_account_decisions(
        _Conn(rows), list_active_accounts=lambda conn: accounts
    )

    assert recorded == len(accounts) * len(rows)
    assert len(classifications) == len(accounts) * len(rows)
    assert profile_loads == accounts
    assert {
        (account_id, external_id)
        for account_id, external_id, _ in classifications
    } == {
        (account_id, row["external_id"])
        for account_id in accounts
        for row in rows
    }


def _evaluation():
    return {
        "lot_score": 1,
        "match": True,
        "lot_id": "lot",
        "geography": {"score": 1, "reason": "ok"},
        "decision": "REVIEW",
        "reason": "test",
        "profile_score": 1,
        "commercial": {},
        "economic_fit": {},
        "capability": {},
        "capability_evidence": [],
        "cpv_evidence": [],
        "hard_capability_blockers": [],
        "explanation": {},
    }


def test_direct_classifier_still_loads_profile_when_none_is_supplied(monkeypatch):
    import funnel_integration

    loaded = []
    seen_profiles = []

    monkeypatch.setattr(
        funnel_integration,
        "load_profile",
        lambda account_id: loaded.append(account_id) or {"account_id": account_id},
    )
    monkeypatch.setattr(
        funnel_integration,
        "evaluate_row",
        lambda item, profile: seen_profiles.append(profile) or _evaluation(),
    )
    monkeypatch.setattr(funnel_integration, "record_decision", lambda *args, **kwargs: None)

    funnel_integration.persist_and_classify(
        object(), {"source": "TEST", "external_id": "1"}, True, account_id="account-a"
    )

    assert loaded == ["account-a"]
    assert seen_profiles == [{"account_id": "account-a"}]


def test_matching_explicit_profile_bypasses_reload(monkeypatch):
    import funnel_integration

    monkeypatch.setattr(
        funnel_integration,
        "load_profile",
        lambda account_id: (_ for _ in ()).throw(AssertionError("profile reloaded")),
    )
    seen = []
    monkeypatch.setattr(
        funnel_integration,
        "evaluate_row",
        lambda item, profile: seen.append(profile) or _evaluation(),
    )
    monkeypatch.setattr(funnel_integration, "record_decision", lambda *args, **kwargs: None)

    profile = {"account_id": "account-b", "marker": "authoritative"}
    funnel_integration.persist_and_classify(
        object(),
        {"source": "TEST", "external_id": "2"},
        True,
        account_id="account-b",
        profile=profile,
    )

    assert seen == [profile]


def test_mismatched_explicit_profile_reloads_authoritative_account(monkeypatch):
    import funnel_integration

    loaded = []
    seen = []

    def load_profile(account_id):
        loaded.append(account_id)
        return {"account_id": account_id, "marker": "reloaded"}

    monkeypatch.setattr(funnel_integration, "load_profile", load_profile)
    monkeypatch.setattr(
        funnel_integration,
        "evaluate_row",
        lambda item, profile: seen.append(profile) or _evaluation(),
    )
    monkeypatch.setattr(funnel_integration, "record_decision", lambda *args, **kwargs: None)

    funnel_integration.persist_and_classify(
        object(),
        {"source": "TEST", "external_id": "3"},
        True,
        account_id="account-b",
        profile={"account_id": "account-a", "marker": "wrong-tenant"},
    )

    assert loaded == ["account-b"]
    assert seen == [{"account_id": "account-b", "marker": "reloaded"}]
