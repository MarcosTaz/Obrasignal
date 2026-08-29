from decimal import Decimal, getcontext

import pytest

from factories.capacity_commitment.evidence import (
    EvidenceKind,
    EvidenceRepository,
    EvidenceSource,
    ExtractedFact,
    FactType,
    ReviewState,
    normalize_confirmed_facts,
    sha256_bytes,
)


def source(tenant="tenant-a", evidence_id="contract-1", **overrides):
    values = dict(
        tenant_id=tenant,
        evidence_id=evidence_id,
        kind=EvidenceKind.CONTRACT,
        display_name="Nomination and LTA.pdf",
        external_ref="customer-data-room:folder-1/document-7",
        sha256=sha256_bytes(b"synthetic contract evidence"),
        captured_at="2026-08-29T20:00:00Z",
    )
    values.update(overrides)
    return EvidenceSource(**values)


def fact(
    fact_id,
    fact_type,
    normalized_value,
    *,
    tenant="tenant-a",
    evidence_id="contract-1",
    raw_value=None,
    scope_ref=None,
    review_state=ReviewState.UNREVIEWED,
):
    return ExtractedFact(
        tenant_id=tenant,
        fact_id=fact_id,
        evidence_id=evidence_id,
        fact_type=fact_type,
        raw_value=raw_value or normalized_value,
        normalized_value=normalized_value,
        scope_ref=scope_ref,
        page_ref="p.12",
        clause_ref="4.2",
        review_state=review_state,
    )


def test_source_is_immutable_idempotent_and_tenant_scoped(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    original = source()
    assert repo.save_source(original) is True
    assert repo.save_source(original) is False
    assert repo.load_source(tenant_id="tenant-a", evidence_id="contract-1") == original

    with pytest.raises(KeyError, match="not found"):
        repo.load_source(tenant_id="tenant-b", evidence_id="contract-1")

    changed = source(display_name="different.pdf")
    with pytest.raises(FileExistsError, match="different provenance"):
        repo.save_source(changed)


def test_source_rejects_secret_bearing_locator_and_invalid_hash(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    with pytest.raises(ValueError, match="query or fragment"):
        repo.save_source(source(external_ref="https://room.example/file?token=secret"))
    with pytest.raises(ValueError, match="sha256"):
        repo.save_source(source(evidence_id="bad-hash", sha256="123"))
    assert repo.list_sources(tenant_id="tenant-a") == []


def test_fact_must_attach_to_source_in_same_tenant(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    repo.save_source(source("tenant-a"))

    with pytest.raises(KeyError, match="not found"):
        repo.save_fact(
            fact(
                "foreign-fact",
                FactType.COMMITTED_UNITS,
                "100000",
                tenant="tenant-b",
            )
        )
    assert repo.list_facts(tenant_id="tenant-b") == []


def test_new_fact_must_start_unreviewed_and_review_is_immutable(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    repo.save_source(source())

    with pytest.raises(ValueError, match="must start UNREVIEWED"):
        repo.save_fact(
            fact(
                "preconfirmed",
                FactType.COMMITTED_UNITS,
                "100000",
                review_state=ReviewState.CONFIRMED,
            )
        )

    item = fact("committed", FactType.COMMITTED_UNITS, "100000")
    assert repo.save_fact(item) is True
    assert repo.save_fact(item) is False
    assert repo.review_fact(
        tenant_id="tenant-a", fact_id="committed", decision=ReviewState.CONFIRMED
    ) is True
    assert repo.review_fact(
        tenant_id="tenant-a", fact_id="committed", decision=ReviewState.CONFIRMED
    ) is False

    with pytest.raises(FileExistsError, match="immutable"):
        repo.review_fact(
            tenant_id="tenant-a", fact_id="committed", decision=ReviewState.REJECTED
        )


def test_unreviewed_and_rejected_facts_never_enter_normalization(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    repo.save_source(source())
    repo.save_fact(fact("unreviewed", FactType.COMMITTED_UNITS, "999999"))
    repo.save_fact(fact("rejected", FactType.DEDICATED_COST, "1000000"))
    repo.review_fact(
        tenant_id="tenant-a", fact_id="rejected", decision=ReviewState.REJECTED
    )

    normalized = normalize_confirmed_facts(repo.list_facts(tenant_id="tenant-a"))
    assert normalized.singleton_values == {}
    assert normalized.actual_units is None
    assert normalized.evidence_refs == ()
    assert normalized.conflicts == ()


def test_confirmed_singletons_normalize_exactly_and_conflicts_fail_closed(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    repo.save_source(source())
    for item in (
        fact("currency", FactType.CURRENCY, "gbp"),
        fact("committed-a", FactType.COMMITTED_UNITS, "100000.00"),
        fact("committed-b", FactType.COMMITTED_UNITS, "90000"),
    ):
        repo.save_fact(item)
        repo.review_fact(
            tenant_id="tenant-a", fact_id=item.fact_id, decision=ReviewState.CONFIRMED
        )

    normalized = normalize_confirmed_facts(repo.list_facts(tenant_id="tenant-a"))
    assert normalized.singleton_values["CURRENCY"] == "GBP"
    assert normalized.singleton_values["COMMITTED_UNITS"] == "100000.00"
    assert normalized.conflict_free is False
    assert "conflicting confirmed COMMITTED_UNITS" in normalized.conflicts


def test_actual_units_require_unique_scope_and_sum_only_confirmed_rows(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    repo.save_source(source(kind=EvidenceKind.ACTUALS))
    rows = (
        fact("row-1", FactType.ACTUAL_UNITS, "1250.25", scope_ref="shipment-1"),
        fact("row-2", FactType.ACTUAL_UNITS, "749.75", scope_ref="shipment-2"),
        fact("row-unreviewed", FactType.ACTUAL_UNITS, "999", scope_ref="shipment-3"),
    )
    for item in rows:
        repo.save_fact(item)
    for fact_id in ("row-1", "row-2"):
        repo.review_fact(
            tenant_id="tenant-a", fact_id=fact_id, decision=ReviewState.CONFIRMED
        )

    normalized = normalize_confirmed_facts(repo.list_facts(tenant_id="tenant-a"))
    assert normalized.actual_units == Decimal("2000.00")
    assert normalized.actual_scopes == ("shipment-1", "shipment-2")
    assert normalized.conflict_free is True


def test_duplicate_actual_scope_blocks_aggregate_instead_of_double_counting(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    repo.save_source(source(kind=EvidenceKind.ACTUALS))
    for item in (
        fact("row-a", FactType.ACTUAL_UNITS, "100", scope_ref="shipment-1"),
        fact("row-b", FactType.ACTUAL_UNITS, "100", scope_ref="shipment-1"),
    ):
        repo.save_fact(item)
        repo.review_fact(
            tenant_id="tenant-a", fact_id=item.fact_id, decision=ReviewState.CONFIRMED
        )

    normalized = normalize_confirmed_facts(repo.list_facts(tenant_id="tenant-a"))
    assert normalized.actual_units is None
    assert normalized.conflict_free is False
    assert normalized.conflicts == ("duplicate confirmed ACTUAL_UNITS scope shipment-1",)


def test_numeric_fact_rejects_float_style_non_exact_inputs(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    repo.save_source(source())
    with pytest.raises(ValueError, match="exact decimal string"):
        repo.save_fact(fact("nan", FactType.DEDICATED_COST, "NaN"))
    with pytest.raises(ValueError, match="finite and non-negative"):
        repo.save_fact(fact("negative", FactType.DEDICATED_COST, "-1"))


def test_actual_normalization_is_not_affected_by_low_global_decimal_precision(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    repo.save_source(source(kind=EvidenceKind.ACTUALS))
    for item in (
        fact("row-1", FactType.ACTUAL_UNITS, "12345678901234567890.25", scope_ref="a"),
        fact("row-2", FactType.ACTUAL_UNITS, "0.75", scope_ref="b"),
    ):
        repo.save_fact(item)
        repo.review_fact(
            tenant_id="tenant-a", fact_id=item.fact_id, decision=ReviewState.CONFIRMED
        )

    old_precision = getcontext().prec
    try:
        getcontext().prec = 6
        normalized = normalize_confirmed_facts(repo.list_facts(tenant_id="tenant-a"))
    finally:
        getcontext().prec = old_precision

    assert normalized.actual_units == Decimal("12345678901234567891.00")


def test_fact_validation_requires_actual_scope_and_strict_boolean_vocabulary(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    repo.save_source(source())
    with pytest.raises(ValueError, match="scope_ref"):
        repo.save_fact(fact("actual-no-scope", FactType.ACTUAL_UNITS, "5"))
    with pytest.raises(ValueError, match="true, false, or unknown"):
        repo.save_fact(fact("bool", FactType.NOTICE_VALID, "yes"))


def test_evidence_lists_are_tenant_isolated(tmp_path):
    repo = EvidenceRepository(str(tmp_path / "capacity.db"))
    repo.save_source(source("tenant-a", "a"))
    repo.save_source(source("tenant-b", "b"))
    repo.save_fact(fact("fa", FactType.CURRENCY, "EUR", tenant="tenant-a", evidence_id="a"))
    repo.save_fact(fact("fb", FactType.CURRENCY, "GBP", tenant="tenant-b", evidence_id="b"))

    assert [item.evidence_id for item in repo.list_sources(tenant_id="tenant-a")] == ["a"]
    assert [item.fact_id for item in repo.list_facts(tenant_id="tenant-a")] == ["fa"]
