from decimal import Decimal
import sqlite3

import pytest

from earnedcash.backup import copy_database, database_fingerprint, restore_verified_copy
from earnedcash.cash_verification import CashEvidence, CashEvidenceKind
from earnedcash.recovery_queue import RecoveryQueueItem
from earnedcash.store import EarnedCashStore


def seeded_store():
    store = EarnedCashStore.memory()
    store.create_company(tenant_id="t1", company_id="co1", name="Alpha Electrical")
    store.create_customer(
        tenant_id="t1", customer_id="cust1", company_id="co1", name="Main Contractor"
    )
    store.create_project(
        tenant_id="t1",
        project_id="p1",
        company_id="co1",
        customer_id="cust1",
        name="Hospital MEP",
        currency="GBP",
    )
    store.create_contract(
        tenant_id="t1",
        contract_id="ct1",
        project_id="p1",
        contract_ref="JCT-001",
        original_value="500000",
    )
    store.replace_recovery_queue(
        tenant_id="t1",
        project_id="p1",
        items=(
            RecoveryQueueItem(
                case_id="invoice:inv1",
                category="INVOICED_DUE_UNPAID",
                amount=Decimal("1000"),
                currency="GBP",
                confidence="HIGH",
                evidence_quality="HIGH",
                blocker="PAYMENT_DELAY",
                action="PREPARE_PAYMENT_EVIDENCE_PACKAGE",
                priority_score=70,
                evidence_chain=("app1", "cert1", "inv1"),
            ),
        ),
    )
    store.record_verified_cash(
        tenant_id="t1",
        project_id="p1",
        receipt_id="receipt-1",
        amount="1000",
        currency="GBP",
        evidence=CashEvidence(
            evidence_ref="bank:tx-1",
            kind=CashEvidenceKind.BANK_RECEIPT,
            tenant_id="t1",
            project_id="p1",
            currency="GBP",
            amount=Decimal("1000"),
            independently_verified=True,
        ),
    )
    return store


def test_backup_is_point_in_time_and_restore_matches_exactly():
    source = seeded_store()
    expected = database_fingerprint(source.connection)

    backup = sqlite3.connect(":memory:")
    copied = copy_database(source.connection, backup)
    assert copied == expected

    source.create_company(tenant_id="t1", company_id="co2", name="Later Mutation")
    assert database_fingerprint(source.connection) != expected
    assert database_fingerprint(backup) == expected

    restored_connection = sqlite3.connect(":memory:")
    restored_fingerprint = restore_verified_copy(
        backup, restored_connection, tenant_ids=("t1",)
    )
    assert restored_fingerprint == expected

    restored = EarnedCashStore(restored_connection)
    assert restored.verified_cash_total(tenant_id="t1", project_id="p1") == Decimal("1000")
    assert restored.list_cases(tenant_id="t1", project_id="p1")[0]["case_id"] == "invoice:inv1"
    assert restored.audit_valid("t1") is True


def test_restore_rejects_backup_with_tampered_audit_chain():
    source = seeded_store()
    backup = sqlite3.connect(":memory:")
    copy_database(source.connection, backup)
    backup.execute(
        "UPDATE earnedcash_audit_events SET payload_json=? WHERE tenant_id=? AND sequence=?",
        ('{"tampered":true}', "t1", 1),
    )
    backup.commit()

    destination = sqlite3.connect(":memory:")
    with pytest.raises(RuntimeError, match="restored_audit_invalid:t1"):
        restore_verified_copy(backup, destination, tenant_ids=("t1",))


def test_backup_and_restore_require_distinct_connections():
    source = sqlite3.connect(":memory:")
    EarnedCashStore(source)
    with pytest.raises(ValueError, match="backup_source_and_destination_must_differ"):
        copy_database(source, source)
    with pytest.raises(ValueError, match="restore_source_and_destination_must_differ"):
        restore_verified_copy(source, source, tenant_ids=())
