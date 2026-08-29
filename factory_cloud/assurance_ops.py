from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from factory_cloud.assurance_store import AssuranceStore
from factory_cloud.recovery_primitives import FeeLineage, RecoveryPrimitiveError
from factory_cloud.state_store import utc_now


class AssuranceOperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OutcomeRecord:
    outcome_id: str
    tenant_id: str
    finding_id: str
    state: str
    recovered_amount: str
    currency: str
    evidence_ref: str
    recorded_at: str


class AssuranceOperations:
    """Durable fail-closed finding review/action/outcome/fee transitions."""

    def __init__(self, store: AssuranceStore):
        self.store = store
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.store.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS recovery_outcomes(
                    outcome_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    recovered_amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_outcome_tenant ON recovery_outcomes(tenant_id,finding_id)")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS recovery_fees(
                    fee_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    outcome_id TEXT NOT NULL,
                    recovered_amount TEXT NOT NULL,
                    fee_rate TEXT NOT NULL,
                    fee_amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    lineage_hash TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fee_tenant ON recovery_fees(tenant_id,outcome_id)")

    def _finding(self, conn: sqlite3.Connection, tenant_id: str, finding_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM findings WHERE tenant_id=? AND finding_id=?", (tenant_id, finding_id)).fetchone()
        if row is None:
            raise AssuranceOperationError("tenant-scoped finding not found")
        return row

    def review(self, *, tenant_id: str, finding_id: str, reviewer: str, approved: bool, reason: str) -> str:
        if not reviewer.strip() or not reason.strip():
            raise AssuranceOperationError("reviewer and reason are required")
        new_state = "APPROVED" if approved else "REJECTED"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._finding(conn, tenant_id, finding_id)
            if row["state"] != "READY_FOR_REVIEW":
                raise AssuranceOperationError("finding is not ready for review")
            conn.execute("UPDATE findings SET state=?, reviewer=?, decision_reason=? WHERE tenant_id=? AND finding_id=?", (new_state, reviewer, reason, tenant_id, finding_id))
            conn.commit()
        return new_state

    def action(self, *, tenant_id: str, finding_id: str) -> str:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._finding(conn, tenant_id, finding_id)
            if row["state"] != "APPROVED":
                raise AssuranceOperationError("only approved findings may be actioned")
            conn.execute("UPDATE findings SET state='ACTIONED' WHERE tenant_id=? AND finding_id=?", (tenant_id, finding_id))
            conn.commit()
        return "ACTIONED"

    def resolve(self, *, tenant_id: str, finding_id: str, outcome_id: str, recovered_amount: str, currency: str, evidence_ref: str) -> OutcomeRecord:
        if not outcome_id.strip() or not currency.strip() or not evidence_ref.strip():
            raise AssuranceOperationError("outcome identity, currency and evidence ref are required")
        try:
            amount = Decimal(recovered_amount)
        except InvalidOperation as exc:
            raise AssuranceOperationError("recovered amount must be decimal") from exc
        if amount < 0:
            raise AssuranceOperationError("recovered amount cannot be negative")
        state = "RECOVERED" if amount > 0 else "CLOSED_NO_RECOVERY"
        recorded_at = utc_now()
        record = OutcomeRecord(outcome_id, tenant_id, finding_id, state, str(amount), currency, evidence_ref, recorded_at)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._finding(conn, tenant_id, finding_id)
            existing = conn.execute("SELECT * FROM recovery_outcomes WHERE outcome_id=?", (outcome_id,)).fetchone()
            if existing is not None:
                comparable = (existing["tenant_id"], existing["finding_id"], existing["state"], existing["recovered_amount"], existing["currency"], existing["evidence_ref"])
                expected = (tenant_id, finding_id, state, str(amount), currency, evidence_ref)
                if comparable != expected:
                    raise AssuranceOperationError("immutable outcome id collision")
                conn.rollback()
                return OutcomeRecord(outcome_id, tenant_id, finding_id, existing["state"], existing["recovered_amount"], existing["currency"], existing["evidence_ref"], existing["recorded_at"])
            if row["state"] != "ACTIONED":
                raise AssuranceOperationError("only actioned findings may be resolved")
            conn.execute("INSERT INTO recovery_outcomes VALUES(?,?,?,?,?,?,?,?)", (outcome_id, tenant_id, finding_id, state, str(amount), currency, evidence_ref, recorded_at))
            conn.execute("UPDATE findings SET state=? WHERE tenant_id=? AND finding_id=?", (state, tenant_id, finding_id))
            conn.commit()
        return record

    def record_fee(self, *, tenant_id: str, outcome_id: str, fee_id: str, fee_rate: str) -> FeeLineage:
        with self._connect() as conn:
            outcome = conn.execute("SELECT * FROM recovery_outcomes WHERE tenant_id=? AND outcome_id=?", (tenant_id, outcome_id)).fetchone()
            if outcome is None:
                raise AssuranceOperationError("tenant-scoped outcome not found")
            if outcome["state"] != "RECOVERED":
                raise AssuranceOperationError("success fee requires recovered outcome")
            try:
                fee = FeeLineage.create(
                    fee_id=fee_id,
                    tenant_id=tenant_id,
                    outcome_id=outcome_id,
                    recovered_amount=outcome["recovered_amount"],
                    fee_rate=fee_rate,
                    currency=outcome["currency"],
                )
            except RecoveryPrimitiveError as exc:
                raise AssuranceOperationError(str(exc)) from exc
            existing = conn.execute("SELECT * FROM recovery_fees WHERE fee_id=?", (fee_id,)).fetchone()
            if existing:
                comparable = (existing["tenant_id"], existing["outcome_id"], existing["recovered_amount"], existing["fee_rate"], existing["fee_amount"], existing["currency"], existing["lineage_hash"])
                expected = (fee.tenant_id, fee.outcome_id, fee.recovered_amount, fee.fee_rate, fee.fee_amount, fee.currency, fee.lineage_hash)
                if comparable != expected:
                    raise AssuranceOperationError("immutable fee id collision")
                return fee
            conn.execute("INSERT INTO recovery_fees VALUES(?,?,?,?,?,?,?,?,?)", (fee.fee_id, fee.tenant_id, fee.outcome_id, fee.recovered_amount, fee.fee_rate, fee.fee_amount, fee.currency, fee.lineage_hash, utc_now()))
            conn.commit()
        return fee

    def get_state(self, *, tenant_id: str, finding_id: str) -> str:
        with self._connect() as conn:
            return str(self._finding(conn, tenant_id, finding_id)["state"])

    def outcomes(self, *, tenant_id: str) -> tuple[OutcomeRecord, ...]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM recovery_outcomes WHERE tenant_id=? ORDER BY recorded_at,outcome_id", (tenant_id,)).fetchall()
        return tuple(OutcomeRecord(**dict(row)) for row in rows)

    def fees(self, *, tenant_id: str) -> tuple[FeeLineage, ...]:
        with self._connect() as conn:
            rows = conn.execute("SELECT fee_id,tenant_id,outcome_id,recovered_amount,fee_rate,fee_amount,currency,lineage_hash FROM recovery_fees WHERE tenant_id=? ORDER BY recorded_at,fee_id", (tenant_id,)).fetchall()
        return tuple(FeeLineage(**dict(row)) for row in rows)
