from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
import pytest

from bangs.money import Money, MoneyError, CurrencyMismatch, sum_money
from bangs.units import convert_quantity, IncompatibleUnitError, UnitError
from bangs.evidence import (
    Availability, EvidenceBasis, FreshnessPolicy, FreshnessState, ProviderEndpointPolicy,
    RequirementBasis, SourceEvidence, TaxBasis, Visibility,
)
from bangs.materials import (
    MaterialPriceObservation, MaterialRequirement, SupplierCandidate, dedupe_observations,
    observation_fingerprint, review_price_outliers,
)

NOW = datetime(2026, 8, 25, 3, 0, tzinfo=timezone.utc)

def ev(basis=EvidenceBasis.MARKET_OBSERVATION, **kw):
    return SourceEvidence("test-source", basis, kw.pop("observed_at", NOW), **kw)

def obs(oid, amount, *, visibility=Visibility.PUBLIC, tenant_id=None, observed_at=NOW):
    return MaterialPriceObservation(
        oid, "mat", "supplier", "m2", Money.of(amount, "EUR"), TaxBasis.VAT_INCLUDED,
        ev(observed_at=observed_at), visibility, tenant_id=tenant_id, availability=Availability.AVAILABLE,
    )

def test_money_is_decimal_nonnegative_and_currency_explicit():
    assert Money.of("10.25", "eur") == Money(Decimal("10.25"), "EUR")
    with pytest.raises(MoneyError): Money.of(-1, "EUR")
    with pytest.raises(MoneyError): Money.of(float("nan"), "EUR")
    with pytest.raises(MoneyError): Money.of(float("inf"), "EUR")
    with pytest.raises(MoneyError): Money.of(1, "EURO")

def test_multi_currency_never_sums_silently():
    with pytest.raises(CurrencyMismatch):
        sum_money((Money.of(1, "EUR"), Money.of(1, "PLN")))

def test_safe_unit_conversions_only():
    assert convert_quantity("1", "t", "kg") == Decimal("1000")
    assert convert_quantity("2000", "kg", "t") == Decimal("2")
    with pytest.raises(IncompatibleUnitError): convert_quantity(1, "m2", "t")
    with pytest.raises(IncompatibleUnitError): convert_quantity(1, "m2", "kg")
    with pytest.raises(UnitError): convert_quantity(1, "", "kg")

def test_material_known_quantity_requires_unit_and_unknown_stays_unknown():
    known = MaterialRequirement("m1", "Board", Decimal("10"), "m2", RequirementBasis.BOQ_EXPLICIT)
    assert known.unit == "m2"
    unknown = MaterialRequirement("m2", "Steel", None, None, RequirementBasis.UNKNOWN)
    assert unknown.quantity is None
    with pytest.raises(ValueError):
        MaterialRequirement("m3", "Bad", Decimal("1"), None, RequirementBasis.USER_SUPPLIED)

def test_list_price_is_not_quote_by_contract():
    list_price = obs("o1", 10)
    quote = MaterialPriceObservation(
        "o2", "mat", "supplier", "m2", Money.of(10, "EUR"), TaxBasis.VAT_INCLUDED,
        ev(EvidenceBasis.SUPPLIER_QUOTE), Visibility.PUBLIC,
    )
    assert list_price.evidence.basis is EvidenceBasis.MARKET_OBSERVATION
    assert quote.evidence.basis is EvidenceBasis.SUPPLIER_QUOTE

def test_private_price_requires_tenant_and_public_cannot_carry_tenant():
    with pytest.raises(ValueError): obs("private", 5, visibility=Visibility.TENANT_PRIVATE)
    with pytest.raises(ValueError): obs("public", 5, visibility=Visibility.PUBLIC, tenant_id="A")
    private = obs("private2", 5, visibility=Visibility.TENANT_PRIVATE, tenant_id="A")
    assert private.tenant_id == "A"

def test_freshness_and_quote_expiration_use_injected_clock():
    evidence = ev(EvidenceBasis.SUPPLIER_QUOTE, observed_at=NOW - timedelta(days=10), valid_until=NOW - timedelta(days=1))
    policy = FreshnessPolicy(timedelta(days=7))
    assert policy.state(evidence, now=NOW) is FreshnessState.EXPIRED
    current = ev(observed_at=NOW - timedelta(days=2))
    assert policy.state(current, now=NOW) is FreshnessState.CURRENT
    stale = ev(observed_at=NOW - timedelta(days=8))
    assert policy.state(stale, now=NOW) is FreshnessState.STALE

def test_dedup_is_exact_and_temporal_history_is_preserved():
    a = obs("a", 10)
    duplicate = obs("a-copy", 10)
    # id is deliberately not part of the content fingerprint.
    assert observation_fingerprint(a) == observation_fingerprint(duplicate)
    later = obs("later", 10, observed_at=NOW + timedelta(hours=1))
    result = dedupe_observations((a, duplicate, later))
    assert len(result) == 2
    assert result[1].evidence.observed_at > result[0].evidence.observed_at

def test_outliers_are_marked_not_removed():
    items = (obs("a", 10), obs("b", 11), obs("c", 100))
    reviews = review_price_outliers(items, ratio_threshold=3)
    assert len(reviews) == 3
    assert [r.state for r in reviews].count("OUTLIER") == 1
    assert reviews[2].observation.observation_id == "c"

def test_provider_endpoint_policy_rejects_ssrf_literals_and_non_allowlisted_hosts():
    policy = ProviderEndpointPolicy(frozenset({"api.example.com"}))
    assert policy.validate("https://api.example.com/v1")
    with pytest.raises(ValueError): policy.validate("http://127.0.0.1/admin")
    with pytest.raises(ValueError): policy.validate("https://evil.example/v1")
    with pytest.raises(ValueError): policy.validate("file:///etc/passwd")

def test_evidence_metadata_rejects_malformed_or_poisoned_inputs():
    with pytest.raises(ValueError): SourceEvidence("bad\x00source", EvidenceBasis.USER_INPUT, NOW)
    with pytest.raises(ValueError): ev(source_url="https://user:pass@example.com/x")
    expired = SourceEvidence("x", EvidenceBasis.SUPPLIER_QUOTE, NOW, valid_until=NOW - timedelta(seconds=1))
    assert FreshnessPolicy(timedelta(days=30)).state(expired, now=NOW) is FreshnessState.EXPIRED


def test_oversized_domain_text_and_unsafe_supplier_url_fail_closed():
    with pytest.raises(ValueError):
        MaterialRequirement("x", "n" * 301, 1, "unit", RequirementBasis.USER_SUPPLIED)
    with pytest.raises(ValueError):
        SupplierCandidate("s", "Supplier", website="file:///etc/passwd")
    with pytest.raises(ValueError):
        MaterialPriceObservation("o", "x", None, "unit", Money.of(1, "EUR"), TaxBasis.VAT_INCLUDED, ev(), Visibility.PUBLIC, flags=tuple("f" for _ in range(51)))
