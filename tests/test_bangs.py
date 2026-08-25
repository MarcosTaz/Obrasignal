import pytest

from bang_commands import BangExecutionContext, BangExecutor, BangPrincipal, BangStatus, ProviderAvailability, ProviderRegistry, ProviderResult, parse_bang
from bang_commands.canonical_providers import canonical_read_provider_registry
from bang_commands.parser import BangParseError, MAX_COMMAND_LENGTH


class FakeProvider:
    name = "fake"
    def __init__(self, *, availability=None, result=None, raises=False):
        self._availability = availability or ProviderAvailability(True)
        self._result = result or ProviderResult(BangStatus.SUCCESS, "ok", {"value": 1}, evidence_refs=("src:1",))
        self.raises = raises; self.calls = []
    def availability(self): return self._availability
    def execute(self, invocation, context):
        self.calls.append((invocation, context))
        if self.raises: raise RuntimeError("boom")
        return self._result


def ctx(account="tenant-a", perms=()): return BangExecutionContext(BangPrincipal(account, frozenset(perms), authenticated=True))
def fixed_executor(providers=None, observer=None): return BangExecutor(providers=providers, observer=observer, clock=lambda: "2026-08-25T00:00:00Z", id_factory=lambda: "exec-1")


def test_known_command_and_alias_parse_deterministically():
    assert parse_bang("!help").command == "help"
    assert parse_bang("!HUNT bridge repair").command == "hunt"
    assert parse_bang("!search 'bridge repair'").args == ("bridge repair",)


def test_malformed_unknown_and_oversized_are_invalid():
    ex = fixed_executor()
    assert ex.execute("!does-not-exist", ctx()).status == BangStatus.INVALID
    assert ex.execute("search foo", ctx()).status == BangStatus.INVALID
    assert ex.execute("!search \"unterminated", ctx()).status == BangStatus.INVALID
    assert ex.execute("!search " + "x" * MAX_COMMAND_LENGTH, ctx()).status == BangStatus.INVALID


@pytest.mark.parametrize("bad", ["!search hi\x00there", "!search hi\nthere", "!search hi\tthere", "!search hi\u202ethere"])
def test_control_and_unicode_format_chars_are_rejected(bad):
    with pytest.raises(BangParseError): parse_bang(bad)


def test_payloads_remain_inert_data():
    for payload in ["; DROP TABLE opportunities", "$(touch /tmp/pwned)", "__import__('os').system('id')", "../../etc/passwd"]:
        assert parse_bang(f'!search "{payload}"').args == (payload,)


@pytest.mark.parametrize("command,permission", [
    ("!search roads --tenant", "opportunities:read"), ("!watch --tenant", "watchlist:write"),
    ("!compare opp-1 --tenant", "opportunities:read"), ("!requirements --tenant", "opportunities:read"),
    ("!readiness --tenant", "opportunities:read"), ("!economics --tenant", "opportunities:read"),
    ("!workspace --tenant", "workspace:read"), ("!buyer --tenant", "opportunities:read"),
    ("!documents --tenant", "opportunities:read"), ("!history --tenant", "opportunities:read"),
    ("!country --tenant", "coverage:read"), ("!source --tenant", "coverage:read"),
])
def test_unknown_flags_are_rejected_for_every_provider_command(command, permission):
    assert fixed_executor().execute(command, ctx(perms={permission})).status == BangStatus.INVALID


def test_missing_capability_fails_closed_as_not_integrated():
    result = fixed_executor().execute("!search roads", ctx(perms={"opportunities:read"}))
    assert result.status == BangStatus.UNAVAILABLE and result.warnings == ("NOT_INTEGRATED",)


def test_gated_capability_and_permission_denied():
    providers = ProviderRegistry(); providers.register("SEARCH", FakeProvider(availability=ProviderAvailability(True, enabled=False, gated=True, reason="flag off")))
    ex = fixed_executor(providers)
    assert ex.execute("!search roads", ctx()).status == BangStatus.FORBIDDEN
    assert ex.execute("!search roads", ctx(perms={"opportunities:read"})).status == BangStatus.GATED


def test_provider_failure_is_failed_not_empty():
    providers = ProviderRegistry(); providers.register("SEARCH", FakeProvider(raises=True))
    result = fixed_executor(providers).execute("!search roads", ctx(perms={"opportunities:read"}))
    assert result.status == BangStatus.FAILED and result.data is None


def test_availability_exception_is_failed_not_unavailable():
    class BrokenAvailability(FakeProvider):
        def availability(self): raise RuntimeError("availability backend failed")
    providers = ProviderRegistry(); providers.register("SEARCH", BrokenAvailability())
    result = fixed_executor(providers).execute("!search roads", ctx(perms={"opportunities:read"}))
    assert result.status == BangStatus.FAILED
    assert result.message == "capability availability check failed"


def test_invalid_availability_contract_is_failed():
    provider = FakeProvider(); provider._availability = object(); providers = ProviderRegistry(); providers.register("SEARCH", provider)
    assert fixed_executor(providers).execute("!search roads", ctx(perms={"opportunities:read"})).status == BangStatus.FAILED


def test_semantically_invalid_availability_contract_is_failed():
    provider = FakeProvider(); provider._availability = ProviderAvailability(present="yes")
    providers = ProviderRegistry(); providers.register("SEARCH", provider)
    assert fixed_executor(providers).execute("!search roads", ctx(perms={"opportunities:read"})).status == BangStatus.FAILED


def test_malformed_provider_result_is_failed_without_escaping_executor():
    malformed = ProviderResult("SUCCESS", "ok")
    provider = FakeProvider(result=malformed); providers = ProviderRegistry(); providers.register("SEARCH", provider)
    result = fixed_executor(providers).execute("!search roads", ctx(perms={"opportunities:read"}))
    assert result.status == BangStatus.FAILED
    assert result.message == "provider returned invalid contract"


def test_malformed_provider_result_collections_are_failed():
    malformed = ProviderResult(BangStatus.SUCCESS, "ok", warnings=["not-a-tuple"])
    provider = FakeProvider(result=malformed); providers = ProviderRegistry(); providers.register("SEARCH", provider)
    assert fixed_executor(providers).execute("!search roads", ctx(perms={"opportunities:read"})).status == BangStatus.FAILED


def test_provider_name_metadata_failure_is_isolated():
    class BrokenName(FakeProvider):
        @property
        def name(self): raise RuntimeError("metadata broken")
    providers = ProviderRegistry(); providers.register("SEARCH", BrokenName())
    assert fixed_executor(providers).execute("!search roads", ctx(perms={"opportunities:read"})).status == BangStatus.SUCCESS


def test_provenance_is_preserved():
    providers = ProviderRegistry(); providers.register("SEARCH", FakeProvider())
    result = fixed_executor(providers).execute("!search roads", ctx(perms={"opportunities:read"}))
    assert result.status == BangStatus.SUCCESS and result.evidence_refs == ("src:1",)


def test_help_only_lists_runtime_available_commands_for_caller():
    providers = ProviderRegistry(); providers.register("SEARCH", FakeProvider())
    result = fixed_executor(providers).execute("!commands", ctx(perms={"opportunities:read"}))
    assert {row["name"] for row in result.data} == {"!help", "!search"}


def test_help_isolates_broken_availability_provider():
    class Broken(FakeProvider):
        def availability(self): raise RuntimeError("broken")
    providers = ProviderRegistry(); providers.register("SEARCH", Broken())
    result = fixed_executor(providers).execute("!help", ctx(perms={"opportunities:read"}))
    assert {row["name"] for row in result.data} == {"!help"}


def test_tenant_identity_comes_from_trusted_context_not_arguments():
    provider = FakeProvider(); providers = ProviderRegistry(); providers.register("WATCHLIST", provider); ex = fixed_executor(providers)
    assert ex.execute("!watch opp-123", ctx(account="tenant-a", perms={"watchlist:write"})).status == BangStatus.SUCCESS
    invocation, execution_context = provider.calls[0]
    assert invocation.args == ("opp-123",) and execution_context.principal.account_id == "tenant-a"
    assert ex.execute("!watch opp-123 tenant-b", ctx(account="tenant-a", perms={"watchlist:write"})).status == BangStatus.INVALID


def test_idempotency_key_is_forwarded_without_bangs_owning_domain_semantics():
    provider = FakeProvider(); providers = ProviderRegistry(); providers.register("WATCHLIST", provider); ex = fixed_executor(providers)
    context = BangExecutionContext(BangPrincipal("tenant-a", frozenset({"watchlist:write"})), idempotency_key="idem-1")
    ex.execute("!watch opp-1", context)
    assert provider.calls[0][1].idempotency_key == "idem-1"


def test_deterministic_semantic_output_with_injected_clock_and_id():
    providers = ProviderRegistry(); providers.register("SEARCH", FakeProvider()); ex = fixed_executor(providers)
    assert ex.execute("!search roads", ctx(perms={"opportunities:read"})).as_dict() == ex.execute("!search roads", ctx(perms={"opportunities:read"})).as_dict()


def test_provider_registry_rejects_duplicate_capability():
    providers = ProviderRegistry(); providers.register("SEARCH", FakeProvider())
    with pytest.raises(ValueError): providers.register("search", FakeProvider())


PROVIDER_CASES = [
    ("SEARCH", "!search roads", "opportunities:read"), ("WATCHLIST", "!watch opp-1", "watchlist:write"),
    ("OPPORTUNITY_COMPARE", "!compare opp-1 opp-2", "opportunities:read"), ("OPPORTUNITY_REQUIREMENTS", "!requirements opp-1", "opportunities:read"),
    ("OPPORTUNITY_READINESS", "!readiness opp-1", "opportunities:read"), ("BID_ECONOMICS", "!economics opp-1", "opportunities:read"),
    ("PURSUIT_WORKSPACE", "!workspace", "workspace:read"), ("BUYER_PROFILE", "!buyer buyer-1", "opportunities:read"),
    ("OPPORTUNITY_DOCUMENTS", "!documents opp-1", "opportunities:read"), ("OPPORTUNITY_HISTORY", "!history opp-1", "opportunities:read"),
    ("COUNTRY_COVERAGE", "!country Portugal", "coverage:read"), ("SOURCE_REGISTRY", "!source TED", "coverage:read"),
]

@pytest.mark.parametrize("capability,command,permission", PROVIDER_CASES)
def test_every_provider_backed_command_happy_unavailable_failure_permission(capability, command, permission):
    assert fixed_executor().execute(command, ctx(perms={permission})).status == BangStatus.UNAVAILABLE
    assert fixed_executor().execute(command, ctx()).status == BangStatus.FORBIDDEN
    providers = ProviderRegistry(); providers.register(capability, FakeProvider())
    assert fixed_executor(providers).execute(command, ctx(perms={permission})).status == BangStatus.SUCCESS
    failing = ProviderRegistry(); failing.register(capability, FakeProvider(raises=True))
    assert fixed_executor(failing).execute(command, ctx(perms={permission})).status == BangStatus.FAILED


@pytest.mark.parametrize("command,permission", [("!search", "opportunities:read"), ("!watch", "watchlist:write"), ("!compare opp-1", "opportunities:read"), ("!requirements", "opportunities:read"), ("!readiness", "opportunities:read"), ("!economics", "opportunities:read"), ("!workspace a b", "workspace:read"), ("!buyer", "opportunities:read"), ("!documents", "opportunities:read"), ("!history", "opportunities:read"), ("!country", "coverage:read"), ("!source", "coverage:read")])
def test_every_provider_backed_command_rejects_wrong_arguments(command, permission):
    assert fixed_executor().execute(command, ctx(perms={permission})).status == BangStatus.INVALID


@pytest.mark.parametrize("capability,command,permission", PROVIDER_CASES)
def test_not_found_status_from_any_provider_is_preserved(capability, command, permission):
    providers = ProviderRegistry(); providers.register(capability, FakeProvider(result=ProviderResult(BangStatus.NOT_FOUND, "not found")))
    assert fixed_executor(providers).execute(command, ctx(perms={permission})).status == BangStatus.NOT_FOUND


def test_observer_never_receives_raw_arguments_or_result_data():
    class Observer:
        def __init__(self): self.events = []
        def record(self, event): self.events.append(dict(event))
    observer = Observer(); providers = ProviderRegistry(); providers.register("SEARCH", FakeProvider())
    ex = fixed_executor(providers, observer=observer)
    ex.execute("!search super-secret-query", ctx(perms={"opportunities:read"}))
    event = observer.events[-1]
    assert "super-secret-query" not in repr(event) and "data" not in event
    assert event["command_type"] == "READ_ONLY"


def test_observer_records_tenant_write_command_type_without_private_payload():
    class Observer:
        def __init__(self): self.events = []
        def record(self, event): self.events.append(dict(event))
    observer = Observer(); providers = ProviderRegistry(); providers.register("WATCHLIST", FakeProvider())
    fixed_executor(providers, observer=observer).execute("!watch opp-secret", ctx(perms={"watchlist:write"}))
    event = observer.events[-1]
    assert event["command_type"] == "TENANT_WRITE"
    assert "opp-secret" not in repr(event)


def test_observer_failure_does_not_break_command_execution():
    class BrokenObserver:
        def record(self, event): raise RuntimeError("telemetry down")
    assert fixed_executor(observer=BrokenObserver()).execute("!help", ctx()).status == BangStatus.SUCCESS


def test_canonical_country_provider_reads_public_market_scope_contract():
    result = fixed_executor(canonical_read_provider_registry()).execute("!country Portugal", ctx(perms={"coverage:read"}))
    assert result.status == BangStatus.SUCCESS
    assert result.data["country"] == "Portugal"
    assert result.data["status"] == "BUILD"
    assert result.data["priority"] == 1
    assert result.evidence_refs == ("registry:market_scope",)


def test_canonical_country_provider_preserves_not_found():
    result = fixed_executor(canonical_read_provider_registry()).execute("!country Atlantis", ctx(perms={"coverage:read"}))
    assert result.status == BangStatus.NOT_FOUND


def test_canonical_source_provider_reads_public_source_registry_contract():
    result = fixed_executor(canonical_read_provider_registry()).execute("!source TED", ctx(perms={"coverage:read"}))
    assert result.status == BangStatus.SUCCESS
    assert result.data["registry_key"] == "TED"
    assert result.data["source_id"] == "eu_ted_search_api"
    assert result.data["production_ready"] is True
    assert result.evidence_refs == ("registry:source_registry:TED",)


def test_canonical_source_provider_reports_registry_gate_without_blocking_read():
    result = fixed_executor(canonical_read_provider_registry()).execute("!source CL_MERCADOPUBLICO", ctx(perms={"coverage:read"}))
    assert result.status == BangStatus.SUCCESS
    assert result.data["production_ready"] is False
    assert "machine_access_not_verified" in result.data["production_gate_reasons"]


def test_canonical_source_provider_preserves_not_found():
    result = fixed_executor(canonical_read_provider_registry()).execute("!source DOES_NOT_EXIST", ctx(perms={"coverage:read"}))
    assert result.status == BangStatus.NOT_FOUND


def test_canonical_read_factory_exposes_only_integrated_country_and_source_commands():
    providers = canonical_read_provider_registry()
    result = fixed_executor(providers).execute("!help", ctx(perms={"coverage:read", "opportunities:read"}))
    assert {row["name"] for row in result.data} == {"!help", "!country", "!source"}
    search = fixed_executor(providers).execute("!search roads", ctx(perms={"opportunities:read"}))
    assert search.status == BangStatus.UNAVAILABLE
    assert search.warnings == ("NOT_INTEGRATED",)
