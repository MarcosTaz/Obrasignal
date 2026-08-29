from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

STATES = ("QUOTED_TEST", "APPROVED_TEST", "INVOICED_TEST", "SETTLED_TEST")


class SyntheticBillingError(RuntimeError):
    pass


@dataclass(frozen=True)
class SyntheticInvoice:
    tenant_id: str
    invoice_id: str
    factory_id: str
    engagement_id: str
    recovery_amount: str
    fee_percent: str
    fee_amount: str
    currency: str
    state: str
    real_revenue: bool


def _money(value: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise SyntheticBillingError("invalid monetary amount") from exc
    if not amount.is_finite() or amount < 0:
        raise SyntheticBillingError("monetary amount must be finite and non-negative")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _percent(value: str) -> Decimal:
    try:
        percent = Decimal(str(value))
    except InvalidOperation as exc:
        raise SyntheticBillingError("invalid fee percent") from exc
    if not percent.is_finite() or percent < 0 or percent > 100:
        raise SyntheticBillingError("fee percent must be between 0 and 100")
    return percent


class SyntheticBillingLedger:
    """Local TEST-only billing lifecycle. Never records or claims real revenue."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS synthetic_invoices(
                    tenant_id TEXT NOT NULL,
                    invoice_id TEXT NOT NULL,
                    factory_id TEXT NOT NULL,
                    engagement_id TEXT NOT NULL,
                    recovery_amount TEXT NOT NULL,
                    fee_percent TEXT NOT NULL,
                    fee_amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    state TEXT NOT NULL,
                    real_revenue INTEGER NOT NULL CHECK(real_revenue=0),
                    created_at TEXT NOT NULL,
                    settled_at TEXT,
                    PRIMARY KEY(tenant_id,invoice_id),
                    UNIQUE(tenant_id,factory_id,engagement_id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row(row: sqlite3.Row) -> SyntheticInvoice:
        return SyntheticInvoice(
            tenant_id=row["tenant_id"], invoice_id=row["invoice_id"], factory_id=row["factory_id"],
            engagement_id=row["engagement_id"], recovery_amount=row["recovery_amount"],
            fee_percent=row["fee_percent"], fee_amount=row["fee_amount"], currency=row["currency"],
            state=row["state"], real_revenue=bool(row["real_revenue"]),
        )

    def quote(
        self, *, tenant_id: str, invoice_id: str, factory_id: str, engagement_id: str,
        recovery_amount: str, fee_percent: str, currency: str,
    ) -> SyntheticInvoice:
        fields = [tenant_id.strip(), invoice_id.strip(), factory_id.strip(), engagement_id.strip(), currency.strip().upper()]
        if any(not value for value in fields):
            raise SyntheticBillingError("billing identity and currency are required")
        if len(fields[-1]) != 3:
            raise SyntheticBillingError("currency must be a three-letter code")
        recovered = _money(recovery_amount)
        percent = _percent(fee_percent)
        fee = (recovered * percent / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO synthetic_invoices VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (fields[0], fields[1], fields[2], fields[3], str(recovered), str(percent), str(fee), fields[4], "QUOTED_TEST", 0, now, None),
                )
        except sqlite3.IntegrityError as exc:
            raise SyntheticBillingError("duplicate synthetic invoice or engagement") from exc
        return self.get(tenant_id=fields[0], invoice_id=fields[1])

    def get(self, *, tenant_id: str, invoice_id: str) -> SyntheticInvoice:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM synthetic_invoices WHERE tenant_id=? AND invoice_id=?",
                (tenant_id.strip(), invoice_id.strip()),
            ).fetchone()
        if not row:
            raise SyntheticBillingError("synthetic invoice not found")
        return self._row(row)

    def transition(self, *, tenant_id: str, invoice_id: str, target: str) -> SyntheticInvoice:
        current = self.get(tenant_id=tenant_id, invoice_id=invoice_id)
        target = target.strip().upper()
        expected = {
            "QUOTED_TEST": "APPROVED_TEST",
            "APPROVED_TEST": "INVOICED_TEST",
            "INVOICED_TEST": "SETTLED_TEST",
        }.get(current.state)
        if target != expected:
            raise SyntheticBillingError(f"invalid synthetic billing transition {current.state}->{target}")
        settled_at = datetime.now(timezone.utc).isoformat() if target == "SETTLED_TEST" else None
        with self._connect() as conn:
            conn.execute(
                "UPDATE synthetic_invoices SET state=?,settled_at=COALESCE(?,settled_at) WHERE tenant_id=? AND invoice_id=?",
                (target, settled_at, current.tenant_id, current.invoice_id),
            )
        return self.get(tenant_id=current.tenant_id, invoice_id=current.invoice_id)
