"""Reusable official Socrata/SODA procurement adapter.

This module deliberately separates transport/pagination from country-specific
normalization. It is intended for official open-data datasets such as Colombia
SECOP and, later, municipal/state procurement datasets that use Socrata.

The adapter uses keyset pagination on (updated timestamp, source identifier)
rather than deep global offsets. Existing watermarks are replayed with a small
overlap so late corrections are re-read safely and de-duplicated by the normal
ObraSignal source/external-id identity.
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

    @property
    def resource_url(self):
        return f"https://{self.domain}/resource/{self.dataset_id}.json"


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

    def _where(self, start_timestamp, after=None):
        updated = self.config.updated_field
        identifier = self.config.id_field
        if after:
            stamp = _escape_soql(after.timestamp)
            ext = _escape_soql(after.external_id)
            return (
                f"({updated} > '{stamp}' OR "
                f"({updated} = '{stamp}' AND {identifier} > '{ext}'))"
            )
        return f"{updated} >= '{_escape_soql(start_timestamp)}'"

    def _params(self, start_timestamp, after=None):
        return {
            "$select": ",".join(self.config.selected_fields),
            "$where": self._where(start_timestamp, after),
            "$order": f"{self.config.updated_field} ASC, {self.config.id_field} ASC",
            "$limit": str(self.config.page_size),
        }

    def fetch_raw_incremental(self, *, watermark=None, now=None):
        """Return raw rows plus a durable high-water cursor.

        Cursor advancement is based on the source's update timestamp. The first
        page starts from either a bounded initial lookback or an overlap before
        the previous watermark. Subsequent pages use keyset pagination.
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
            last = batch[-1]
            stamp = str(last.get(self.config.updated_field) or "").strip()
            ext = str(last.get(self.config.id_field) or "").strip()
            if not stamp or not ext:
                raise RuntimeError(
                    f"{self.config.source} cannot advance cursor: missing "
                    f"{self.config.updated_field}/{self.config.id_field}"
                )
            next_after = SocrataCursor(stamp, ext)
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

        cursor = None
        if rows:
            last = rows[-1]
            cursor = SocrataCursor(
                str(last.get(self.config.updated_field) or ""),
                str(last.get(self.config.id_field) or ""),
            ).encode()
        return rows, cursor

    def fetch_incremental(self, normalizer, *, watermark=None, now=None):
        raw, cursor = self.fetch_raw_incremental(watermark=watermark, now=now)
        normalized = []
        for row in raw:
            item = normalizer(row)
            if item and item.get("external_id"):
                normalized.append(item)
        return normalized, cursor
