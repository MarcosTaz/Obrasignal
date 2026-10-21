"""Serbia Public Procurement Portal TECH_LAB probe.

This is deliberately not a production connector. It provides a deterministic,
fail-closed parser/normalizer for publisher-exported JSON records while the
supported machine-route and commercial-reuse gates are being verified.

No CAPTCHA, authenticated/private endpoint, or undocumented endpoint bypass is
implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Iterable, Mapping


SERBIA_ISO2 = "RS"
SERBIA_ISO3 = "SRB"
SOURCE_ID = "RS:PUBLIC_PROCUREMENT_OFFICE:PUBLIC_PROCUREMENT_PORTAL"

# CPV division 45 = Construction work. Keep filtering source-native; Serbian
# free-text keywords are intentionally not used as the primary discriminator.
CONSTRUCTION_CPV_PREFIX = "45"


class SerbiaExportSchemaError(ValueError):
    """Raised when an export cannot be normalized without guessing semantics."""


@dataclass(frozen=True)
class SerbiaProcurementRecord:
    procedure_id: str
    signal_type: str
    title: str
    cpv_codes: tuple[str, ...]
    published_at: str | None
    updated_at: str | None
    buyer_id: str | None
    lot_id: str | None
    source_id: str = SOURCE_ID

    @property
    def logical_id(self) -> str:
        parts = (self.source_id, self.procedure_id, self.signal_type, self.lot_id or "")
        return sha256("|".join(parts).encode("utf-8")).hexdigest()

    @property
    def is_construction(self) -> bool:
        return any(code.startswith(CONSTRUCTION_CPV_PREFIX) for code in self.cpv_codes)

    @property
    def incremental_timestamp(self) -> str | None:
        return self.updated_at or self.published_at


def _first(record: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = record.get(name)
        if value not in (None, ""):
            return value
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _cpv_codes(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raw = value.replace(";", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        raw = value
    else:
        raw = (value,)
    result: list[str] = []
    for item in raw:
        if isinstance(item, Mapping):
            item = _first(item, "code", "cpvCode", "CPV")
        text = _text(item)
        if not text:
            continue
        # Preserve publisher value except harmless whitespace/hyphen formatting.
        normalized = text.replace(" ", "").split("-")[0]
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def _signal_type(record: Mapping[str, Any]) -> str:
    raw = (_text(_first(record, "signalType", "type", "noticeType", "documentType")) or "").lower()
    mapping = {
        "plan": "PROCUREMENT_PLAN",
        "procurement plan": "PROCUREMENT_PLAN",
        "prior information notice": "FORECAST",
        "tender": "TENDER",
        "contract notice": "TENDER",
        "award": "AWARD",
        "award decision": "AWARD",
        "contract": "CONTRACT",
        "contract amendment": "AMENDMENT",
        "amendment": "AMENDMENT",
    }
    if raw in mapping:
        return mapping[raw]
    raise SerbiaExportSchemaError(f"unsupported/unknown Serbian export signal type: {raw!r}")


def normalize_export_record(record: Mapping[str, Any]) -> SerbiaProcurementRecord:
    """Normalize one public export record without inventing missing identity."""
    procedure_id = _text(_first(record, "procedureId", "procedureID", "procurementId", "id"))
    title = _text(_first(record, "title", "procurementTitle", "name"))
    if not procedure_id:
        raise SerbiaExportSchemaError("stable procedure identifier is required")
    if not title:
        raise SerbiaExportSchemaError("title is required")

    return SerbiaProcurementRecord(
        procedure_id=procedure_id,
        signal_type=_signal_type(record),
        title=title,
        cpv_codes=_cpv_codes(_first(record, "cpvCodes", "cpvCode", "CPV")),
        published_at=_text(_first(record, "publishedAt", "publicationDate", "published")),
        updated_at=_text(_first(record, "updatedAt", "modifiedAt", "lastModified")),
        buyer_id=_text(_first(record, "buyerId", "contractingAuthorityId", "buyerIdentifier")),
        lot_id=_text(_first(record, "lotId", "lotID")),
    )


def normalize_export(records: Iterable[Mapping[str, Any]]) -> list[SerbiaProcurementRecord]:
    return [normalize_export_record(record) for record in records]


def incremental_cursor(records: Iterable[SerbiaProcurementRecord]) -> str | None:
    """Return max publisher timestamp; never synthesize a cursor from local time."""
    values = [record.incremental_timestamp for record in records if record.incremental_timestamp]
    return max(values) if values else None


def probe_summary(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = normalize_export(records)
    return {
        "country": SERBIA_ISO2,
        "source_id": SOURCE_ID,
        "records": len(normalized),
        "construction_records": sum(item.is_construction for item in normalized),
        "signal_types": sorted({item.signal_type for item in normalized}),
        "incremental_cursor": incremental_cursor(normalized),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "production_ready": False,
    }
