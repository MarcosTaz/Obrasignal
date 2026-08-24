"""Reusable adapter for official rolling ZIP+JSON procurement snapshots.

Some procurement publishers regenerate a monthly JSON ZIP every day instead of
exposing an immutable daily file or an updated-since API. A normal completed
cursor is unsafe for that shape because the current month's artifact can change
after it has already been read. This adapter therefore stores the last successful
*observation* date and re-reads a bounded set of recent month snapshots once per
publisher-local day.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import PurePosixPath
from zoneinfo import ZoneInfo
import zipfile

import requests


@dataclass(frozen=True)
class RollingSnapshotConfig:
    source: str
    timezone_name: str
    lookback_months: int = 2
    refresh_after_local_hour: int = 6
    timeout: int = 90
    max_compressed_bytes: int = 32 * 1024 * 1024
    max_uncompressed_bytes: int = 192 * 1024 * 1024
    max_zip_entries: int = 2
    user_agent: str = "ObraSignal official procurement snapshot connector/1.0"


@dataclass(frozen=True)
class RollingSnapshotCursor:
    last_observed_local_date: str
    observed_at: str | None = None

    def encode(self):
        return json.dumps(
            {
                "last_observed_local_date": self.last_observed_local_date,
                "observed_at": self.observed_at,
            },
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
                stamp = str(payload.get("last_observed_local_date") or "").strip()
                date.fromisoformat(stamp)
                observed_at = payload.get("observed_at")
                return cls(stamp, str(observed_at).strip() if observed_at else None)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        try:
            date.fromisoformat(text[:10])
        except ValueError:
            return None
        return cls(text[:10], None)


def _aware_now(value):
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _month_shift(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _recent_months(local_day, count):
    result = []
    for offset in range(max(1, int(count))):
        result.append(_month_shift(local_day.year, local_day.month, -offset))
    return result


def _safe_member(info):
    name = str(info.filename or "")
    path = PurePosixPath(name)
    if not name or name.endswith("/"):
        raise RuntimeError("snapshot ZIP contains an empty/directory member")
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"snapshot ZIP contains unsafe member path: {name}")
    if path.suffix.lower() != ".json":
        raise RuntimeError(f"snapshot ZIP member is not JSON: {name}")
    return name


def _published_stamp(row):
    if not isinstance(row, dict):
        return ""
    for key in ("source_updated_at", "published_at", "publication_date"):
        value = row.get(key)
        if value:
            return str(value)
    return ""


class OfficialZipJSONSnapshotAdapter:
    def __init__(self, config, *, url_factory, normalizer, session=None):
        self.config = config
        self.url_factory = url_factory
        self.normalizer = normalizer
        self.session = session or requests.Session()
        try:
            self.local_timezone = ZoneInfo(config.timezone_name)
        except Exception as exc:
            raise ValueError(f"invalid snapshot timezone {config.timezone_name}") from exc

    def _headers(self):
        return {
            "Accept": "application/zip, application/json;q=0.9, */*;q=0.5",
            "User-Agent": self.config.user_agent,
        }

    def _fetch_month(self, year, month, *, now):
        url = self.url_factory(year, month)
        response = self.session.get(
            url,
            headers=self._headers(),
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        body = response.content
        if not body:
            raise RuntimeError(f"{self.config.source} snapshot {year}-{month:02d} returned empty body")
        if len(body) > int(self.config.max_compressed_bytes):
            raise RuntimeError(
                f"{self.config.source} snapshot {year}-{month:02d} compressed bytes={len(body)} "
                f"above max_compressed_bytes={self.config.max_compressed_bytes}"
            )
        if body[:2] != b"PK":
            raise RuntimeError(f"{self.config.source} snapshot {year}-{month:02d} is not a ZIP archive")

        try:
            archive = zipfile.ZipFile(BytesIO(body))
        except zipfile.BadZipFile as exc:
            raise RuntimeError(f"{self.config.source} snapshot {year}-{month:02d} is an invalid ZIP") from exc

        with archive:
            infos = archive.infolist()
            if not infos:
                raise RuntimeError(f"{self.config.source} snapshot {year}-{month:02d} ZIP is empty")
            if len(infos) > int(self.config.max_zip_entries):
                raise RuntimeError(
                    f"{self.config.source} snapshot {year}-{month:02d} has {len(infos)} ZIP entries, "
                    f"above max_zip_entries={self.config.max_zip_entries}"
                )
            json_infos = []
            total_uncompressed = 0
            for info in infos:
                _safe_member(info)
                total_uncompressed += int(info.file_size or 0)
                if total_uncompressed > int(self.config.max_uncompressed_bytes):
                    raise RuntimeError(
                        f"{self.config.source} snapshot {year}-{month:02d} uncompressed bytes={total_uncompressed} "
                        f"above max_uncompressed_bytes={self.config.max_uncompressed_bytes}"
                    )
                json_infos.append(info)
            if len(json_infos) != 1:
                raise RuntimeError(
                    f"{self.config.source} snapshot {year}-{month:02d} expected exactly one JSON member, "
                    f"got {len(json_infos)}"
                )
            raw = archive.read(json_infos[0])

        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{self.config.source} snapshot {year}-{month:02d} contains invalid JSON") from exc
        if not isinstance(payload, list):
            raise RuntimeError(
                f"{self.config.source} snapshot {year}-{month:02d} JSON root must be a list, "
                f"got {type(payload).__name__}"
            )

        rows = []
        for unit in payload:
            if not isinstance(unit, dict):
                continue
            normalized = self.normalizer(unit, now=now)
            if normalized is None:
                continue
            if isinstance(normalized, list):
                candidates = normalized
            else:
                candidates = [normalized]
            for item in candidates:
                if isinstance(item, dict) and item.get("external_id"):
                    rows.append(item)
        return rows

    def _should_fetch(self, cursor, local_now):
        if not cursor:
            return True
        try:
            observed = date.fromisoformat(cursor.last_observed_local_date)
        except ValueError:
            return True
        today = local_now.date()
        if observed >= today:
            return False
        refresh_hour = min(23, max(0, int(self.config.refresh_after_local_hour)))
        if local_now.hour < refresh_hour and observed >= today - timedelta(days=1):
            return False
        return True

    def fetch_incremental(self, *, watermark=None, now=None):
        current_utc = _aware_now(now)
        local_now = current_utc.astimezone(self.local_timezone)
        cursor = RollingSnapshotCursor.decode(watermark)
        if not self._should_fetch(cursor, local_now):
            return [], cursor.encode() if cursor else watermark

        rows = []
        for year, month in _recent_months(local_now.date(), self.config.lookback_months):
            rows.extend(self._fetch_month(year, month, now=current_utc))

        # The same OCID may be represented in more than one rolling snapshot.
        # Prefer the source's most recently updated normalized representation.
        latest = {}
        order = []
        for row in rows:
            key = str(row.get("external_id") or "").strip()
            if not key:
                continue
            if key not in latest:
                order.append(key)
                latest[key] = row
                continue
            if _published_stamp(row) >= _published_stamp(latest[key]):
                latest[key] = row

        refresh_hour = min(23, max(0, int(self.config.refresh_after_local_hour)))
        observed_day = local_now.date()
        if local_now.hour < refresh_hour:
            # An early bootstrap is useful, but it must not suppress the normal
            # post-refresh observation later on the same local day.
            observed_day = observed_day - timedelta(days=1)
        new_cursor = RollingSnapshotCursor(
            observed_day.isoformat(),
            current_utc.isoformat().replace("+00:00", "Z"),
        ).encode()
        return [latest[key] for key in order], new_cursor
