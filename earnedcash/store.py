from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import sqlite3

from .audit import AuditEvent, append_event, verify_history
from .case_workflow import CaseState, transition_case as validate_case_transition
from .cash_verification import CashEvidence, CashVerificationState, verify_cash_evidence
from .recovery_queue import RecoveryQueueItem


ZERO = Decimal("0")


def _money(value: Decimal | str) -> Decimal:
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid money value") from None
    if not parsed.is_finite() or parsed < ZERO:
        raise ValueError("invalid money value")
    return parsed


class EarnedCashStore:
    """Tenant-safe persistence boundary for assisted-pilot workflows.

    The caller owns the SQLite connection/path. Nothing here wires EarnedCash to
    the ObraSignal production database or deployment.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.ensure_schema()

    @classmethod
    def memory(cls) -> "EarnedCashStore":
        return cls(sqlite3.connect(":memory:"))

    def ensure_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS earnedcash_companies (
                tenant_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                name TEXT NOT NULL,
                PRIMARY KEY (tenant_id, company_id)
            );
            CREATE TABLE IF NOT EXISTS earnedcash_customers (
                tenant_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                name TEXT NOT NULL,
                PRIMARY KEY (tenant_id, customer_id)
            );
            CREATE TABLE IF NOT EXISTS earnedcash_projects (
                tenant_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                name TEXT NOT NULL,
                currency TEXT NOT NULL,
                PRIMARY KEY (tenant_id, project_id)
            );
            CREATE TABLE IF NOT EXISTS earnedcash_contracts (
                tenant_id TEXT NOT NULL,
                contract_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                contract_ref TEXT NOT NULL,
                original_value TEXT NOT NULL,
                PRIMARY KEY (tenant_id, contract_id)
            );
            CREATE TABLE IF NOT EXISTS earnedcash_cases (
                tenant_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                category TEXT NOT NULL,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                confidence TEXT NOT NULL,
                evidence_quality TEXT NOT NULL,
                blocker TEXT,
                action TEXT NOT NULL,
                priority_score INTEGER NOT NULL,
                evidence_chain_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                PRIMARY KEY (tenant_id, project_id, case_id)
            );
            CREATE TABLE IF NOT EXISTS earnedcash_cash_receipts (
                tenant_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                receipt_id TEXT NOT NULL,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                evidence_ref TEXT NOT NULL,
                verified INTEGER NOT NULL,
                PRIMARY KEY (tenant_id, receipt_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS earnedcash_unique_cash_evidence
                ON earnedcash_cash_receipts (tenant_id, evidence_ref);
            CREATE TABLE IF NOT EXISTS earnedcash_audit_events (
                tenant_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT,
                event_hash TEXT NOT NULL,
                PRIMARY KEY (tenant_id, sequence)
            );
            """
        )
        self.connection.commit()

    def _required(self, value: str, field: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError(f"{field} is required")
        return value

    def _exists(self, table: str, tenant_id: str, id_field: str, value: str) -> bool:
        row = self.connection.execute(
            f"SELECT 1 FROM {table} WHERE tenant_id=? AND {id_field}=?",
            (tenant_id, value),
        ).fetchone()
        return row is not None

    def _audit(self, tenant_id: str, event_type: str, entity_id: str, payload: dict) -> None:
        history = self.audit_history(tenant_id)
        updated = append_event(
            history,
            tenant_id=tenant_id,
            event_type=event_type,
            entity_id=entity_id,
            payload=payload,
        )
        event = updated[-1]
        self.connection.execute(
            """INSERT INTO earnedcash_audit_events
               (tenant_id, sequence, event_type, entity_id, payload_json,
                previous_hash, event_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                event.tenant_id,
                event.sequence,
                event.event_type,
                event.entity_id,
                json.dumps(event.payload, sort_keys=True, separators=(",", ":")),
                event.previous_hash,
                event.event_hash,
            ),
        )

    def create_company(self, *, tenant_id: str, company_id: str, name: str) -> None:
        tenant_id = self._required(tenant_id, "tenant_id")
        company_id = self._required(company_id, "company_id")
        name = self._required(name, "name")
        with self.connection:
            self.connection.execute(
                "INSERT INTO earnedcash_companies (tenant_id, company_id, name) VALUES (?, ?, ?)",
                (tenant_id, company_id, name),
            )
            self._audit(tenant_id, "COMPANY_CREATED", company_id, {"name": name})

    def create_customer(
        self, *, tenant_id: str, customer_id: str, company_id: str, name: str
    ) -> None:
        if not self._exists("earnedcash_companies", tenant_id, "company_id", company_id):
            raise ValueError("company_not_found_for_tenant")
        customer_id = self._required(customer_id, "customer_id")
        name = self._required(name, "name")
        with self.connection:
            self.connection.execute(
                """INSERT INTO earnedcash_customers
                   (tenant_id, customer_id, company_id, name) VALUES (?, ?, ?, ?)""",
                (tenant_id, customer_id, company_id, name),
            )
            self._audit(
                tenant_id, "CUSTOMER_CREATED", customer_id,
                {"company_id": company_id, "name": name},
            )

    def create_project(
        self, *, tenant_id: str, project_id: str, company_id: str,
        customer_id: str, name: str, currency: str
    ) -> None:
        if not self._exists("earnedcash_companies", tenant_id, "company_id", company_id):
            raise ValueError("company_not_found_for_tenant")
        customer = self.connection.execute(
            """SELECT company_id FROM earnedcash_customers
               WHERE tenant_id=? AND customer_id=?""",
            (tenant_id, customer_id),
        ).fetchone()
        if customer is None:
            raise ValueError("customer_not_found_for_tenant")
        if customer["company_id"] != company_id:
            raise ValueError("customer_company_mismatch")
        project_id = self._required(project_id, "project_id")
        name = self._required(name, "name")
        currency = self._required(currency, "currency").upper()
        with self.connection:
            self.connection.execute(
                """INSERT INTO earnedcash_projects
                   (tenant_id, project_id, company_id, customer_id, name, currency)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tenant_id, project_id, company_id, customer_id, name, currency),
            )
            self._audit(
                tenant_id, "PROJECT_CREATED", project_id,
                {"company_id": company_id, "customer_id": customer_id,
                 "name": name, "currency": currency},
            )

    def create_contract(
        self, *, tenant_id: str, contract_id: str, project_id: str,
        contract_ref: str, original_value: Decimal | str
    ) -> None:
        if not self._exists("earnedcash_projects", tenant_id, "project_id", project_id):
            raise ValueError("project_not_found_for_tenant")
        contract_id = self._required(contract_id, "contract_id")
        contract_ref = self._required(contract_ref, "contract_ref")
        value = _money(original_value)
        with self.connection:
            self.connection.execute(
                """INSERT INTO earnedcash_contracts
                   (tenant_id, contract_id, project_id, contract_ref, original_value)
                   VALUES (?, ?, ?, ?, ?)""",
                (tenant_id, contract_id, project_id, contract_ref, str(value)),
            )
            self._audit(
                tenant_id, "CONTRACT_CREATED", contract_id,
                {"project_id": project_id, "contract_ref": contract_ref,
                 "original_value": str(value)},
            )

    def replace_recovery_queue(
        self, *, tenant_id: str, project_id: str,
        items: tuple[RecoveryQueueItem, ...]
    ) -> None:
        project = self.connection.execute(
            "SELECT currency FROM earnedcash_projects WHERE tenant_id=? AND project_id=?",
            (tenant_id, project_id),
        ).fetchone()
        if project is None:
            raise ValueError("project_not_found_for_tenant")
        project_currency = project["currency"]
        if any(item.currency != project_currency for item in items):
            raise ValueError("case_currency_mismatch")
        progressed = self.connection.execute(
            """SELECT 1 FROM earnedcash_cases
               WHERE tenant_id=? AND project_id=? AND status<>'OPEN' LIMIT 1""",
            (tenant_id, project_id),
        ).fetchone()
        if progressed is not None:
            raise ValueError("progressed_case_requires_review_before_reconcile")
        with self.connection:
            self.connection.execute(
                "DELETE FROM earnedcash_cases WHERE tenant_id=? AND project_id=?",
                (tenant_id, project_id),
            )
            for item in items:
                self.connection.execute(
                    """INSERT INTO earnedcash_cases
                       (tenant_id, project_id, case_id, category, amount, currency,
                        confidence, evidence_quality, blocker, action, priority_score,
                        evidence_chain_json, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')""",
                    (
                        tenant_id, project_id, item.case_id, item.category,
                        str(_money(item.amount)), item.currency, item.confidence,
                        item.evidence_quality, item.blocker, item.action,
                        item.priority_score, json.dumps(list(item.evidence_chain)),
                    ),
                )
            self._audit(
                tenant_id, "RECOVERY_QUEUE_REPLACED", project_id,
                {"case_ids": [item.case_id for item in items]},
            )

    def list_cases(self, *, tenant_id: str, project_id: str) -> list[dict]:
        rows = self.connection.execute(
            """SELECT case_id, category, amount, currency, confidence,
                      evidence_quality, blocker, action, priority_score,
                      evidence_chain_json, status
               FROM earnedcash_cases
               WHERE tenant_id=? AND project_id=?
               ORDER BY priority_score DESC, CAST(amount AS REAL) DESC, case_id""",
            (tenant_id, project_id),
        ).fetchall()
        return [
            {
                "case_id": row["case_id"],
                "category": row["category"],
                "amount": row["amount"],
                "currency": row["currency"],
                "confidence": row["confidence"],
                "evidence_quality": row["evidence_quality"],
                "blocker": row["blocker"],
                "action": row["action"],
                "priority_score": row["priority_score"],
                "evidence_chain": json.loads(row["evidence_chain_json"]),
                "status": row["status"],
            }
            for row in rows
        ]

    def _verified_cash_insert(
        self, *, tenant_id: str, project_id: str, receipt_id: str,
        amount: Decimal, currency: str, evidence_ref: str
    ) -> None:
        self.connection.execute(
            """INSERT INTO earnedcash_cash_receipts
               (tenant_id, project_id, receipt_id, amount, currency,
                evidence_ref, verified)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (tenant_id, project_id, receipt_id, str(amount), currency, evidence_ref),
        )
        self._audit(
            tenant_id, "VERIFIED_CASH_RECORDED", receipt_id,
            {"project_id": project_id, "amount": str(amount),
             "currency": currency, "evidence_ref": evidence_ref},
        )

    def record_verified_cash(
        self, *, tenant_id: str, project_id: str, receipt_id: str,
        amount: Decimal | str, currency: str, evidence: CashEvidence
    ) -> None:
        project = self.connection.execute(
            "SELECT currency FROM earnedcash_projects WHERE tenant_id=? AND project_id=?",
            (tenant_id, project_id),
        ).fetchone()
        if project is None:
            raise ValueError("project_not_found_for_tenant")
        receipt_id = self._required(receipt_id, "receipt_id")
        currency = self._required(currency, "currency").upper()
        if currency != project["currency"]:
            raise ValueError("cash_currency_mismatch")
        value = _money(amount)
        verification = verify_cash_evidence(
            tenant_id=tenant_id,
            project_id=project_id,
            currency=currency,
            claimed_amount=value,
            evidence=evidence,
        )
        if verification.state != CashVerificationState.VERIFIED:
            raise ValueError(f"cash_evidence_not_verified:{verification.reason}")
        evidence_ref = self._required(verification.evidence_ref or "", "evidence_ref")
        with self.connection:
            self._verified_cash_insert(
                tenant_id=tenant_id,
                project_id=project_id,
                receipt_id=receipt_id,
                amount=value,
                currency=currency,
                evidence_ref=evidence_ref,
            )

    def transition_case(
        self, *, tenant_id: str, project_id: str, case_id: str,
        target: CaseState, customer_approved: bool = False,
        settlement_evidence_verified: bool = False,
        receipt_id: str | None = None,
        cash_evidence: CashEvidence | None = None,
    ) -> None:
        row = self.connection.execute(
            """SELECT amount, currency, status FROM earnedcash_cases
               WHERE tenant_id=? AND project_id=? AND case_id=?""",
            (tenant_id, project_id, case_id),
        ).fetchone()
        if row is None:
            raise ValueError("case_not_found_for_tenant_project")
        current = CaseState(row["status"])
        amount = _money(row["amount"])
        cash_verified = False
        verified_ref: str | None = None
        if target == CaseState.PAID:
            if cash_evidence is None or receipt_id is None:
                raise ValueError("verified cash evidence required")
            verification = verify_cash_evidence(
                tenant_id=tenant_id,
                project_id=project_id,
                currency=row["currency"],
                claimed_amount=amount,
                evidence=cash_evidence,
            )
            cash_verified = verification.state == CashVerificationState.VERIFIED
            verified_ref = verification.evidence_ref
            if not cash_verified:
                raise ValueError(f"cash_evidence_not_verified:{verification.reason}")
            receipt_id = self._required(receipt_id, "receipt_id")

        validate_case_transition(
            current=current,
            target=target,
            amount=amount,
            customer_approved=customer_approved,
            settlement_evidence_verified=settlement_evidence_verified,
            cash_evidence_verified=cash_verified,
        )

        with self.connection:
            self.connection.execute(
                """UPDATE earnedcash_cases SET status=?
                   WHERE tenant_id=? AND project_id=? AND case_id=?""",
                (target.value, tenant_id, project_id, case_id),
            )
            self._audit(
                tenant_id,
                "CASE_STATE_CHANGED",
                case_id,
                {
                    "project_id": project_id,
                    "from": current.value,
                    "to": target.value,
                    "customer_approved": bool(customer_approved),
                    "settlement_evidence_verified": bool(settlement_evidence_verified),
                    "cash_evidence_ref": verified_ref,
                },
            )
            if target == CaseState.PAID:
                self._verified_cash_insert(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    receipt_id=receipt_id or "",
                    amount=amount,
                    currency=row["currency"],
                    evidence_ref=self._required(verified_ref or "", "evidence_ref"),
                )

    def verified_cash_total(self, *, tenant_id: str, project_id: str) -> Decimal:
        rows = self.connection.execute(
            """SELECT amount FROM earnedcash_cash_receipts
               WHERE tenant_id=? AND project_id=? AND verified=1""",
            (tenant_id, project_id),
        ).fetchall()
        return sum((_money(row["amount"]) for row in rows), ZERO)

    def audit_history(self, tenant_id: str) -> tuple[AuditEvent, ...]:
        rows = self.connection.execute(
            """SELECT sequence, event_type, entity_id, payload_json,
                      previous_hash, event_hash
               FROM earnedcash_audit_events
               WHERE tenant_id=? ORDER BY sequence""",
            (tenant_id,),
        ).fetchall()
        return tuple(
            AuditEvent(
                sequence=row["sequence"],
                tenant_id=tenant_id,
                event_type=row["event_type"],
                entity_id=row["entity_id"],
                payload=json.loads(row["payload_json"]),
                previous_hash=row["previous_hash"],
                event_hash=row["event_hash"],
            )
            for row in rows
        )

    def audit_valid(self, tenant_id: str) -> bool:
        return verify_history(self.audit_history(tenant_id), tenant_id=tenant_id)
