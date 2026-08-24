"""Reusable official Socrata/SODA procurement adapter.

This module deliberately separates transport/pagination from country-specific
normalization. It is intended for official open-data datasets such as Colombia
SECOP and, later, municipal/state procurement datasets that use Socrata.

The adapter uses keyset pagination on (effective source timestamp, source
identifier) rather than deep global offsets. Sources with incomplete update
columns may provide a documented SoQL cursor expression (for example a
``greatest(update_at, published_at)`` expression) without changing the generic
pagination contract.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json

import requests


@dataclass(frozen=True)
class SocrataSourceConfig:
    source: str
    country: str
    domain: str
    dataset_id: str
    id_field: str
    updated_field: str
    selected_fields: tuple[str, ...]
    page_size: int = 1000
    max_pages: int = 50
    initial_lookback_days: int = 7
    overlap_minutes: int = 1440
    app_token_env: str | None = None
    market: str = "GLOBAL"
    base_where: str = ""
    cursor_expression: str = ""
    cursor_alias: str = "source_cursor_at"

    @property
    def resource_url(self):
        return f"https://{self.domain}/resource/{self.dataset_id}.json"

    @property
    def cursor_sql(self):
        return str(self.cursor_expression or self.updated_field).strip()

    @property
    def cursor_result_field(self):
        if self.cursor_expression:
            return str(self.cursor_alias or "source_cursor_at").strip()
        return self.updated_field

    @property
    def select_fields(self):
        fields = list(self.selected_fields)
        if self.cursor_expression:
            alias = self.cursor_result_field
            fields.append(f"{self.cursor_sql} AS {alias}")
        return tuple(fields)


@dataclass(frozen=True)
class SocrataCursor:
    timestamp: str
    external_id: str = ""

    def encode(self):
        return json.dumps(
            {"timestamp": self.timestamp, "external_id": self.external_id},
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def decode(cls, value):
        if not value:
            return None
        text = str(value).strip()
        if text.startswith("{"):
            try:
                payload = json.loads(text)
                stamp = str(payload.get("timestamp") or "").strip()
                if stamp:
                    return cls(stamp, str(payload.get("external_id") or ""))
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        # Backwards-compatible timestamp-only watermark.
        return cls(text, "")


def _escape_soql(value):
    return str(value or "").replace("'", "''")


def _parse_timestamp(value):
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _socrata_timestamp(value):
    parsed = value if isinstance(value, datetime) else _parse_timestamp(value)
    if parsed is None:
        return str(value or "")
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


class SocrataProcurementAdapter:
    def __init__(self, config, *, session=None, timeout=45, app_token=None):
        self.config = config
        self.session = session or requests.Session()
        self.timeout = timeout
        self.app_token = app_token

    def _headers(self):
        return {"X-App-Token": self.app_token} if self.app_token else {}

    def _start_timestamp(self, watermark, now):
        cursor = SocrataCursor.decode(watermark)
        if cursor:
            parsed = _parse_timestamp(cursor.timestamp)
            if parsed:
                return _socrata_timestamp(parsed - timedelta(minutes=self.config.overlap_minutes))
            return cursor.timestamp
        anchor = now or datetime.now(timezone.utc)
        return _socrata_timestamp(anchor - timedelta(days=self.config.initial_lookback_days))

    def _incremental_where(self, start_timestamp, after=None):
        cursor_sql = self.config.cursor_sql
        identifier = self.config.id_field
        if after:
            stamp = _escape_soql(after.timestamp)
            ext = _escape_soql(after.external_id)
            return (
                f"({cursor_sql} > '{stamp}' OR "
                f"({cursor_sql} = '{stamp}' AND {identifier} > '{ext}'))"
            )
        return f"{cursor_sql} >= '{_escape_soql(start_timestamp)}'"

    def _where(self, start_timestamp, after=None):
        incremental = self._incremental_where(start_timestamp, after)
        base = str(self.config.base_where or "").strip()
        if not base:
            return incremental
        return f"({base}) AND ({incremental})"

    def _params(self, start_timestamp, after=None):
        return {
            "$select": ",".join(self.config.select_fields),
            "$where": self._where(start_timestamp, after),
            "$order": f"{self.config.cursor_sql} ASC, {self.config.id_field} ASC",
            "$limit": str(self.config.page_size),
        }

    def _cursor_from_row(self, row):
        stamp = str(row.get(self.config.cursor_result_field) or "").strip()
        ext = str(row.get(self.config.id_field) or "").strip()
        if not stamp or not ext:
            raise RuntimeError(
                f"{self.config.source} cannot advance cursor: missing "
                f"{self.config.cursor_result_field}/{self.config.id_field}"
            )
        return SocrataCursor(stamp, ext)

    def fetch_raw_incremental(self, *, watermark=None, now=None):
        """Return raw rows plus a durable high-water cursor.

        Cursor advancement is based on the source's effective cursor timestamp.
        The first page starts from either a bounded initial lookback or an overlap
        before the previous watermark. Subsequent pages use keyset pagination.
        """
        start_timestamp = self._start_timestamp(watermark, now)
        after = None
        rows = []
        for _ in range(max(1, self.config.max_pages)):
            response = self.session.get(
                self.config.resource_url,
                params=self._params(start_timestamp, after),
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            batch = response.json()
            if not isinstance(batch, list):
                raise RuntimeError(f"{self.config.source} Socrata response is not a list")
            if not batch:
                break
            rows.extend(row for row in batch if isinstance(row, dict))
            next_after = self._cursor_from_row(batch[-1])
            if after == next_after:
                raise RuntimeError(f"{self.config.source} Socrata cursor did not advance")
            after = next_after
            if len(batch) < self.config.page_size:
                break
        else:
            raise RuntimeError(
                f"{self.config.source} reached max_pages={self.config.max_pages}; "
                "sync window must be narrowed before advancing the watermark"
            )

        cursor = self._cursor_from_row(rows[-1]).encode() if rows else None
        return rows, cursor

    def fetch_incremental(self, normalizer, *, watermark=None, now=None):
        raw, cursor = self.fetch_raw_incremental(watermark=watermark, now=now)
        normalized = []
        for row in raw:
            item = normalizer(row)
            if item and item.get("external_id"):
                normalized.append(item)
        return normalized, cursor
