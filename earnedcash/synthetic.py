from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .ledger import LedgerKind, LedgerRecord


@dataclass(frozen=True)
class SyntheticCompany:
    name: str
    records: tuple[LedgerRecord, ...]
    oracle_verified_cash: Decimal
    oracle_due_unpaid: Decimal
    oracle_not_yet_due: Decimal
    oracle_unknown: Decimal
    oracle_p0: int


def _record(rid, kind, amount, tenant, customer, project, currency, relates_to=None, verified=True, due=None):
    return LedgerRecord(rid, tenant, customer, project, currency, kind, Decimal(amount), relates_to, verified, due)


def _chain(prefix, amount, tenant, customer, project, currency, due, payment=None, payment_verified=True):
    app, cert, inv = f"{prefix}-app", f"{prefix}-cert", f"{prefix}-inv"
    rows = [
        _record(app, LedgerKind.APPLICATION, amount, tenant, customer, project, currency),
        _record(cert, LedgerKind.CERTIFICATE, amount, tenant, customer, project, currency, app),
        _record(inv, LedgerKind.INVOICE, amount, tenant, customer, project, currency, cert, True, due),
    ]
    if payment is not None:
        rows.append(_record(f"{prefix}-pay", LedgerKind.PAYMENT, payment, tenant, customer, project, currency, inv, payment_verified))
    return tuple(rows)


def diversified_companies() -> tuple[SyntheticCompany, ...]:
    alpha = _chain("alpha1", "100000", "alpha", "gc-a", "hospital", "GBP", True, "60000")
    nova = _chain("nova1", "80000", "nova", "gc-b", "office", "EUR", False)
    prime = _chain("prime1", "50000", "prime", "gc-c", "fitout", "GBP", True, "50000")
    titan = _chain("titan1", "120000", "titan", "gc-d", "plant", "USD", None)
    legacy = _chain("legacy1", "45000", "legacy", "gc-e", "school", "GBP", True, "10000", False)
    redteam = (
        _record("rt-app", LedgerKind.APPLICATION, "70000", "rt-a", "gc-f", "tower", "GBP"),
        _record("rt-cert", LedgerKind.CERTIFICATE, "70000", "rt-b", "gc-f", "tower", "GBP", "rt-app"),
        _record("rt-inv", LedgerKind.INVOICE, "70000", "rt-b", "gc-f", "tower", "GBP", "rt-cert", True, True),
    )
    return (
        SyntheticCompany("ALPHA ELECTRICAL", alpha, Decimal("60000"), Decimal("40000"), Decimal("0"), Decimal("0"), 0),
        SyntheticCompany("NOVA HVAC", nova, Decimal("0"), Decimal("0"), Decimal("80000"), Decimal("0"), 0),
        SyntheticCompany("PRIME INTERIORS", prime, Decimal("50000"), Decimal("0"), Decimal("0"), Decimal("0"), 0),
        SyntheticCompany("TITAN MEP", titan, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("120000"), 0),
        SyntheticCompany("LEGACY CONSTRUCTION", legacy, Decimal("0"), Decimal("35000"), Decimal("0"), Decimal("0"), 0),
        SyntheticCompany("REDTEAM CONTRACTING", redteam, Decimal("0"), Decimal("0"), Decimal("0"), Decimal("70000"), 1),
    )
