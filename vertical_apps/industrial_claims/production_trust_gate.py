from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable, Mapping, Protocol


class ProductionTrustGateError(RuntimeError):
    """Real confidential intake is not currently safe to enable."""


@dataclass(frozen=True)
class ControlReceipt:
    """A bounded, secret-free result from a live external control check."""

    control: str
    verified: bool
    provider: str
    reference: str | None
    checked_at: datetime
    valid_until: datetime

    def __post_init__(self) -> None:
        if self.control not in {"worm", "timestamp"}:
            raise ValueError("unsupported production trust control")
        if self.checked_at.tzinfo is None or self.valid_until.tzinfo is None:
            raise ValueError("control receipt timestamps must be timezone-aware")
        if self.valid_until <= self.checked_at:
            raise ValueError("control receipt validity interval is invalid")
        provider = str(self.provider or "").strip()
        if not provider or len(provider) > 128:
            raise ValueError("control receipt provider is invalid")
        if self.verified and not str(self.reference or "").strip():
            raise ValueError("verified control receipt requires provider reference")


class ControlProbe(Protocol):
    def __call__(self) -> ControlReceipt:
        ...


@dataclass(frozen=True)
class ProductionTrustDecision:
    ready: bool
    blockers: tuple[str, ...]
    checked_at: datetime
    valid_until: datetime | None
    providers: Mapping[str, str]

    def as_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "blockers": list(self.blockers),
            "checked_at": self.checked_at.isoformat(),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "providers": dict(self.providers),
            "real_confidential_intake_allowed": self.ready,
            "fail_closed": True,
        }


class ProductionTrustGate:
    """Automatically fail-close real intake when MFA/WORM/QTSP evidence is absent.

    MFA is evaluated from the already signature-verified JWT claims for every
    request. WORM and qualified timestamp state come only from live control probes;
    environment-variable declarations are deliberately insufficient. Successful
    external checks are cached for a short bounded interval. An outage, expiry,
    malformed receipt or failed re-check closes the gate automatically.
    """

    def __init__(
        self,
        *,
        worm_probe: ControlProbe,
        timestamp_probe: ControlProbe,
        cache_ttl: timedelta = timedelta(minutes=5),
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if cache_ttl <= timedelta(0) or cache_ttl > timedelta(hours=1):
            raise ValueError("production trust cache_ttl must be between zero and one hour")
        self._worm_probe = worm_probe
        self._timestamp_probe = timestamp_probe
        self._cache_ttl = cache_ttl
        self._clock = clock
        self._cached_controls: dict[str, ControlReceipt] = {}
        self._cache_expires_at: datetime | None = None
        self._lock = Lock()

    @staticmethod
    def _mfa_ready(claims: Mapping[str, object] | None) -> bool:
        return isinstance(claims, Mapping) and claims.get("aal") == "aal2"

    def _fresh_controls(self, now: datetime) -> dict[str, ControlReceipt]:
        with self._lock:
            if (
                self._cache_expires_at is not None
                and now < self._cache_expires_at
                and set(self._cached_controls) == {"worm", "timestamp"}
                and all(receipt.verified and now < receipt.valid_until for receipt in self._cached_controls.values())
            ):
                return dict(self._cached_controls)

            receipts: dict[str, ControlReceipt] = {}
            for expected, probe in (("worm", self._worm_probe), ("timestamp", self._timestamp_probe)):
                try:
                    receipt = probe()
                except Exception:
                    receipt = ControlReceipt(
                        control=expected,
                        verified=False,
                        provider="UNAVAILABLE",
                        reference=None,
                        checked_at=now,
                        valid_until=now + min(self._cache_ttl, timedelta(minutes=1)),
                    )
                if receipt.control != expected:
                    raise ProductionTrustGateError(f"{expected} probe returned the wrong control identity")
                receipts[expected] = receipt

            upper_bound = now + self._cache_ttl
            self._cache_expires_at = min(
                upper_bound,
                *(receipt.valid_until.astimezone(timezone.utc) for receipt in receipts.values()),
            )
            self._cached_controls = receipts
            return dict(receipts)

    def evaluate(self, *, verified_claims: Mapping[str, object] | None) -> ProductionTrustDecision:
        now = self._clock().astimezone(timezone.utc)
        blockers: list[str] = []
        if not self._mfa_ready(verified_claims):
            blockers.append("mfa_aal2_required")

        try:
            controls = self._fresh_controls(now)
        except ProductionTrustGateError:
            controls = {}
            blockers.append("control_identity_invalid")

        providers: dict[str, str] = {}
        valid_until: datetime | None = None
        for control in ("worm", "timestamp"):
            receipt = controls.get(control)
            if receipt is None:
                blockers.append(f"{control}_unverified")
                continue
            providers[control] = receipt.provider
            if not receipt.verified or now >= receipt.valid_until.astimezone(timezone.utc):
                blockers.append(f"{control}_unverified")
                continue
            expiry = receipt.valid_until.astimezone(timezone.utc)
            valid_until = expiry if valid_until is None else min(valid_until, expiry)

        return ProductionTrustDecision(
            ready=not blockers,
            blockers=tuple(dict.fromkeys(blockers)),
            checked_at=now,
            valid_until=valid_until if not blockers else None,
            providers=providers,
        )

    def require_ready(self, *, verified_claims: Mapping[str, object] | None) -> ProductionTrustDecision:
        decision = self.evaluate(verified_claims=verified_claims)
        if not decision.ready:
            raise ProductionTrustGateError(
                "real confidential intake blocked: " + ",".join(decision.blockers)
            )
        return decision

    def invalidate(self) -> None:
        """Force the next request to re-run both external provider checks."""
        with self._lock:
            self._cached_controls = {}
            self._cache_expires_at = None
