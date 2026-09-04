from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

from vertical_apps.industrial_claims.recovery_reconciliation_store import (
    PersistedRecoveryReconciliation,
)


class RecoveryPortfolioError(ValueError):
    pass


_AMOUNT_FIELDS = (
    "net_documented_exposure",
    "evidence_supported",
    "claimed",
    "approved",
    "settled",
    "unsupported_exposure",
    "supported_unclaimed",
    "claimed_unapproved",
    "approved_unsettled",
    "supported_unsettled",
)


@dataclass(frozen=True)
class PortfolioRecoveryRollup:
    tenant_id: str
    currency: str
    case_count: int
    amounts: dict[str, Decimal]
    signal_counts: dict[str, int]
    finding_hashes: tuple[tuple[str, str], ...]
    portfolio_hash: str

    def as_dict(self) -> dict[str, object]:
        return {
            "tenant_id": self.tenant_id,
            "currency": self.currency,
            "case_count": self.case_count,
            "amounts": {key: str(value) for key, value in self.amounts.items()},
            "signal_counts": dict(self.signal_counts),
            "finding_hashes": [
                {"finding_id": finding_id, "reconciliation_hash": reconciliation_hash}
                for finding_id, reconciliation_hash in self.finding_hashes
            ],
            "portfolio_hash": self.portfolio_hash,
            "cross_currency_aggregation_performed": False,
            "legal_entitlement_established": False,
        }


def _decimal(value: object, *, field: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise RecoveryPortfolioError(f"invalid reconciliation amount: {field}") from exc
    if not amount.is_finite() or amount < 0:
        raise RecoveryPortfolioError(f"invalid reconciliation amount: {field}")
    return amount


def rollup_recovery_portfolio(
    *,
    tenant_id: str,
    records: Iterable[PersistedRecoveryReconciliation],
) -> PortfolioRecoveryRollup:
    tenant = str(tenant_id or "").strip()
    if not tenant:
        raise RecoveryPortfolioError("tenant_id is required")

    material = tuple(records)
    if not material:
        raise RecoveryPortfolioError("portfolio requires at least one persisted reconciliation")

    finding_ids: set[str] = set()
    currencies: set[str] = set()
    totals = {field: Decimal("0") for field in _AMOUNT_FIELDS}
    signal_counts: dict[str, int] = {}
    finding_hashes: list[tuple[str, str]] = []

    for record in material:
        if not isinstance(record, PersistedRecoveryReconciliation):
            raise RecoveryPortfolioError("portfolio records must be persisted reconciliations")
        if record.tenant_id != tenant:
            raise RecoveryPortfolioError("cross-tenant portfolio aggregation denied")
        if record.finding_id in finding_ids:
            raise RecoveryPortfolioError("duplicate finding_id would double count recovery")
        finding_ids.add(record.finding_id)

        payload = record.snapshot
        currency = str(payload.get("currency") or "").strip().upper()
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise RecoveryPortfolioError("persisted reconciliation currency is invalid")
        currencies.add(currency)

        for field in _AMOUNT_FIELDS:
            if field not in payload:
                raise RecoveryPortfolioError(f"persisted reconciliation missing {field}")
            totals[field] += _decimal(payload[field], field=field)

        signals = payload.get("signals")
        if not isinstance(signals, list):
            raise RecoveryPortfolioError("persisted reconciliation signals are invalid")
        for signal in signals:
            key = str(signal or "").strip()
            if not key:
                raise RecoveryPortfolioError("persisted reconciliation signal is invalid")
            signal_counts[key] = signal_counts.get(key, 0) + 1

        finding_hashes.append((record.finding_id, record.reconciliation_hash))

    if len(currencies) != 1:
        raise RecoveryPortfolioError("cross-currency aggregation is prohibited without an explicit FX evidence layer")
    currency = next(iter(currencies))
    ordered_hashes = tuple(sorted(finding_hashes))
    digest_payload = {
        "tenant_id": tenant,
        "currency": currency,
        "finding_hashes": ordered_hashes,
        "amounts": {field: str(totals[field]) for field in _AMOUNT_FIELDS},
    }
    portfolio_hash = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return PortfolioRecoveryRollup(
        tenant_id=tenant,
        currency=currency,
        case_count=len(material),
        amounts=totals,
        signal_counts=dict(sorted(signal_counts.items())),
        finding_hashes=ordered_hashes,
        portfolio_hash=portfolio_hash,
    )
