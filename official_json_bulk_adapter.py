"""Reusable bounded adapter for official daily JSON bulk procurement datasets.

The adapter treats a dated bulk file as the atomic unit of progress. A cursor is
advanced only after the complete file was fetched, parsed and normalized. Missing
expected files and malformed payloads fail closed so an outage cannot be mistaken
for a legitimate zero-result day.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json

import requests


@dataclass(frozen=True)
class OfficialJSONBulkConfig:
    source: str
    country: str
    url_factory: object
    initial_lookback_days: int = 3
    overlap_days: int = 1
    max_days_per_sync: int = 7
    publication_lag_days: int = 1
    timeout: int = 45
    market: str = "GLOBAL"


@dataclass(frozen=True)
class DailyBulkCursor:
    completed_through: str

    def encode(self):
        return json.dumps(
            {"completed_through": self.completed_through},
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
                stamp = str(payload.get("completed_through") or "").strip()
                if date.fromisoformat(stamp):
                    return cls(stamp)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        try:
            return cls(date.fromisoformat(text[:10]).isoformat())
        except ValueError:
            return None


def _utc_date(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    if value:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            pass
    return None


def _list_payload(payload):
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "items", "notices", "records", "results"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise RuntimeError("official JSON bulk payload is not a supported notice list")


class OfficialJSONBulkAdapter:
    def __init__(self, config, *, normalizer, session=None, headers=None):
        self.config = config
        self.normalizer = normalizer
        self.session = session or requests.Session()
        self.headers = dict(headers or {})

    def _target_end(self, now):
        today = _utc_date(now or datetime.now(timezone.utc))
        return today - timedelta(days=max(0, int(self.config.publication_lag_days)))

    def _start_date(self, watermark, target_end):
        cursor = DailyBulkCursor.decode(watermark)
        if cursor:
            completed = _utc_date(cursor.completed_through)
            if completed:
                return completed + timedelta(days=1) - timedelta(days=max(0, int(self.config.overlap_days)))
        return target_end - timedelta(days=max(0, int(self.config.initial_lookback_days)))

    def _days(self, watermark, now):
        end = self._target_end(now)
        current = self._start_date(watermark, end)
        count = 0
        while current <= end and count < max(1, int(self.config.max_days_per_sync)):
            yield current
            current += timedelta(days=1)
            count += 1

    def _fetch_day(self, day):
        url = self.config.url_factory(day)
        response = self.session.get(url, headers=self.headers, timeout=self.config.timeout)
        # A dated file is expected once it falls inside the connector's eligible
        # publication horizon. Never silently skip a 404/empty response: that
        # would create an irreversible cursor gap during source degradation.
        response.raise_for_status()
        if not response.content or not response.content.strip():
            raise RuntimeError(f"{self.config.source} bulk file {day} was empty; cursor not advanced")
        try:
            payload = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{self.config.source} bulk file {day} was invalid JSON; cursor not advanced") from exc
        return _list_payload(payload)

    def fetch_incremental(self, *, watermark=None, now=None):
        rows = []
        cursor = None
        for day in self._days(watermark, now):
            notices = self._fetch_day(day)
            for notice in notices:
                normalized = self.normalizer(notice, publication_day=day, now=now)
                if not normalized:
                    continue
                if isinstance(normalized, dict):
                    normalized = [normalized]
                if not isinstance(normalized, list):
                    raise RuntimeError(f"{self.config.source} normalizer returned unsupported type")
                for item in normalized:
                    if isinstance(item, dict) and item.get("external_id"):
                        rows.append(item)
            cursor = DailyBulkCursor(day.isoformat()).encode()
        return rows, cursor
