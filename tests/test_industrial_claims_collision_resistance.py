from vertical_apps.industrial_claims.service import IndustrialClaimsService


def _analyze(
    service,
    *,
    tenant_id,
    event_ref,
    customer_ref="oem",
    program_ref="program",
    basis_ref="basis",
    cost_ref=None,
    basis_content="signed tooling agreement",
    event_content="documented cancellation event",
    cost_content="cost ledger supporting tooling exposure",
):
    return service.analyze(
        tenant_id=tenant_id,
        actor_id="analyst",
        customer_ref=customer_ref,
        program_ref=program_ref,
        event_ref=event_ref,
        claim_family="TOOLING",
        commercial_basis_ref=basis_ref,
        cost_evidence_ref=cost_ref or f"cost-{event_ref}",
        gross_cost="10000",
        currency="EUR",
        commercial_basis_content=basis_content,
        event_evidence_content=event_content,
        cost_evidence_content=cost_content,
        notice_deadline_not_applicable=True,
    )


def _action(service, result):
    service.review(
        tenant_id=result.tenant_id,
        finding_id=result.finding.finding_id,
        reviewer="reviewer",
        approved=True,
        reason="reviewed for internal workflow",
    )
    service.action(
        tenant_id=result.tenant_id,
        finding_id=result.finding.finding_id,
        actor_id="operator",
    )


def test_structured_contract_reference_prevents_delimiter_collision(tmp_path):
    first_service = IndustrialClaimsService(tmp_path / "first.sqlite3")
    second_service = IndustrialClaimsService(tmp_path / "second.sqlite3")

    first = _analyze(
        first_service,
        tenant_id="alpha",
        event_ref="same-event",
        customer_ref="a:b",
        program_ref="c",
        basis_ref="d",
    )
    second = _analyze(
        second_service,
        tenant_id="alpha",
        event_ref="same-event",
        customer_ref="a",
        program_ref="b:c",
        basis_ref="d",
    )

    assert first.fingerprint.contract_ref != second.fingerprint.contract_ref
    assert first.fingerprint.fingerprint != second.fingerprint.fingerprint


def test_fingerprint_derived_case_ids_allow_same_event_and_family_across_distinct_contracts(tmp_path):
    service = IndustrialClaimsService(tmp_path / "same-event-contracts.sqlite3")

    first = _analyze(
        service,
        tenant_id="alpha",
        event_ref="shared-event-reference",
        customer_ref="oem-a",
        program_ref="program-a",
        basis_ref="basis-a",
        cost_ref="cost-a",
        basis_content="signed agreement A",
        cost_content="cost ledger A",
    )
    second = _analyze(
        service,
        tenant_id="alpha",
        event_ref="shared-event-reference",
        customer_ref="oem-b",
        program_ref="program-b",
        basis_ref="basis-b",
        cost_ref="cost-b",
        basis_content="signed agreement B",
        cost_content="cost ledger B",
    )

    assert first.is_new_recovery is True
    assert second.is_new_recovery is True
    assert first.fingerprint.fingerprint != second.fingerprint.fingerprint
    assert first.finding.finding_id != second.finding.finding_id
    assert first.finding.finding_id.endswith(":finding")
    assert second.finding.finding_id.endswith(":finding")
    assert first.fingerprint.fingerprint in first.finding.finding_id
    assert second.fingerprint.fingerprint in second.finding.finding_id
    assert service.store.count("findings", "alpha") == 2
    assert service.case_store.count("alpha") == 2
    assert service.index.count_fingerprints("alpha") == 2

    replay = _analyze(
        service,
        tenant_id="alpha",
        event_ref="shared-event-reference",
        customer_ref="oem-a",
        program_ref="program-a",
        basis_ref="basis-a",
        cost_ref="cost-a",
        basis_content="signed agreement A",
        cost_content="cost ledger A",
    )
    assert replay.is_new_recovery is False
    assert replay.finding.finding_id == first.finding.finding_id
    assert replay.fingerprint.fingerprint == first.fingerprint.fingerprint
    assert service.store.count("findings", "alpha") == 2


def test_case_scoped_evidence_ids_allow_reused_human_refs_across_distinct_contracts(tmp_path):
    service = IndustrialClaimsService(tmp_path / "reused-evidence-refs.sqlite3")

    first = _analyze(
        service,
        tenant_id="alpha",
        event_ref="shared-event-ref",
        customer_ref="oem-a",
        program_ref="program-a",
        basis_ref="shared-basis-ref",
        cost_ref="shared-cost-ref",
        basis_content="agreement content for contract A",
        event_content="event evidence for contract A",
        cost_content="cost evidence for contract A",
    )
    second = _analyze(
        service,
        tenant_id="alpha",
        event_ref="shared-event-ref",
        customer_ref="oem-b",
        program_ref="program-b",
        basis_ref="shared-basis-ref",
        cost_ref="shared-cost-ref",
        basis_content="different agreement content for contract B",
        event_content="different event evidence for contract B",
        cost_content="different cost evidence for contract B",
    )

    assert first.fingerprint.fingerprint != second.fingerprint.fingerprint
    assert {item.source_ref for item in first.evidence} == {"shared-basis-ref", "shared-event-ref", "shared-cost-ref"}
    assert {item.source_ref for item in second.evidence} == {"shared-basis-ref", "shared-event-ref", "shared-cost-ref"}
    assert set(first.finding.evidence_ids).isdisjoint(set(second.finding.evidence_ids))
    assert all(first.fingerprint.fingerprint in evidence_id for evidence_id in first.finding.evidence_ids)
    assert all(second.fingerprint.fingerprint in evidence_id for evidence_id in second.finding.evidence_ids)
    assert service.store.count("evidence", "alpha") == 6
    assert service.store.count("findings", "alpha") == 2


def test_same_external_outcome_id_is_isolated_across_tenants(tmp_path):
    service = IndustrialClaimsService(tmp_path / "outcome-tenants.sqlite3")
    alpha = _analyze(service, tenant_id="alpha", event_ref="event-alpha")
    beta = _analyze(service, tenant_id="beta", event_ref="event-beta")
    _action(service, alpha)
    _action(service, beta)

    alpha_outcome = service.resolve(
        tenant_id="alpha",
        finding_id=alpha.finding.finding_id,
        outcome_id="settlement-1",
        recovered_amount="5000",
        currency="EUR",
        evidence_ref="bank-alpha",
        evidence_content="alpha settlement evidence",
        actor_id="operator",
    )
    beta_outcome = service.resolve(
        tenant_id="beta",
        finding_id=beta.finding.finding_id,
        outcome_id="settlement-1",
        recovered_amount="4000",
        currency="EUR",
        evidence_ref="bank-beta",
        evidence_content="beta settlement evidence",
        actor_id="operator",
    )

    assert alpha_outcome.outcome_id == "alpha:settlement-1"
    assert beta_outcome.outcome_id == "beta:settlement-1"
    assert alpha_outcome.outcome_id != beta_outcome.outcome_id
    assert len(service.ops.outcomes(tenant_id="alpha")) == 1
    assert len(service.ops.outcomes(tenant_id="beta")) == 1
