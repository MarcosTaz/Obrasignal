"""Reusable OCDS adapter for APIs that paginate with an opaque cursor link.

The source cursor used inside one result window is deliberately not persisted.
ObraSignal persists only the completed temporal window after every source page in
that window has been read successfully. This prevents an ephemeral publisher
cursor from becoming durable product state.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import json
from urllib.parse import parse_qs, urlsplit

import requests


@dataclass(frozen=True)
class OCDSOpaqueCursorConfig:
    source: str
    country: str
    search_url: str
    page_size: int = 100
    page_size_param: str = "limit"
    cursor_param: str = "cursor"
    max_pages_per_window: int = 100
    window_days: int = 1
    max_windows_per_sync: int = 31
    initial_lookback_days: int = 7
    overlap_days: int = 1
    market: str = "GLOBAL"
    timeout: int = 45


@dataclass(frozen=True)
class OCDSOpaqueWindowCursor:
    completed_through: str

    def encode(self):
        return json.dumps({"completed_through": self.completed_through}, separators=(",", ":"), sort_keys=True)

    @classmethod
    def decode(cls, value):
        if not value:
            return None
        text = str(value).strip()
        if text.startswith("{"):
            try:
                payload = json.loads(text)
                stamp = str(payload.get("completed_through") or "").strip()
                date.fromisoformat(stamp[:10])
                return cls(stamp[:10])
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        try:
            return cls(date.fromisoformat(text[:10]).isoformat())
        except ValueError:
            return None


def _date(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _release_rows(payload):
    if not isinstance(payload, dict):
        raise RuntimeError("opaque-cursor OCDS response is not an object")
    releases = payload.get("releases")
    if releases is None:
        raise RuntimeError("opaque-cursor OCDS response has no releases array")
    if not isinstance(releases, list):
        raise RuntimeError("opaque-cursor OCDS releases is not a list")
    return [row for row in releases if isinstance(row, dict)]


def _next_cursor(payload, *, search_url, cursor_param):
    links = payload.get("links") if isinstance(payload, dict) else None
    next_url = links.get("next") if isinstance(links, dict) else None
    if not next_url:
        return None
    parsed_next = urlsplit(str(next_url))
    parsed_base = urlsplit(search_url)
    # Do not follow arbitrary URLs supplied in response data. The publisher may
    # vary query parameters, but scheme/host/path must remain the configured API.
    if parsed_next.scheme != parsed_base.scheme or parsed_next.netloc != parsed_base.netloc or parsed_next.path != parsed_base.path:
        raise RuntimeError("opaque-cursor OCDS next link escaped configured API endpoint")
    values = parse_qs(parsed_next.query).get(cursor_param) or []
    token = str(values[0]).strip() if values else ""
    if not token:
        raise RuntimeError("opaque-cursor OCDS next link did not contain cursor token")
    return token


class OCDSOpaqueCursorAdapter:
    def __init__(self, config, *, params_factory, normalizer, session=None, headers=None):
        self.config = config
        self.params_factory = params_factory
        self.normalizer = normalizer
        self.session = session or requests.Session()
        self.headers = dict(headers or {})

    def _start_date(self, watermark, today):
        cursor = OCDSOpaqueWindowCursor.decode(watermark)
        if cursor:
            completed = _date(cursor.completed_through)
            if completed:
                return completed + timedelta(days=1) - timedelta(days=max(0, int(self.config.overlap_days)))
        return today - timedelta(days=max(0, int(self.config.initial_lookback_days)))

    def _windows(self, watermark, now):
        today = _date(now or datetime.now(timezone.utc))
        start = self._start_date(watermark, today)
        width = max(1, int(self.config.window_days))
        count = 0
        while start <= today and count < max(1, int(self.config.max_windows_per_sync)):
            end = min(today, start + timedelta(days=width - 1))
            yield start, end
            start = end + timedelta(days=1)
            count += 1

    def _fetch_window(self, start, end):
        base_params = dict(self.params_factory(start, end) or {})
        base_params[self.config.page_size_param] = str(max(1, int(self.config.page_size)))
        token = None
        seen_tokens = set()
        releases = []
        for page in range(1, max(1, int(self.config.max_pages_per_window)) + 1):
            params = dict(base_params)
            if token:
                params[self.config.cursor_param] = token
            response = self.session.get(self.config.search_url, params=params, headers=self.headers, timeout=self.config.timeout)
            response.raise_for_status()
            payload = response.json()
            batch = _release_rows(payload)
            next_token = _next_cursor(payload, search_url=self.config.search_url, cursor_param=self.config.cursor_param)
            if next_token and not batch:
                raise RuntimeError(f"{self.config.source} returned empty page with a next cursor; window not complete")
            releases.extend(batch)
            if not next_token:
                return releases
            if next_token == token or next_token in seen_tokens:
                raise RuntimeError(f"{self.config.source} repeated opaque cursor; refusing pagination loop")
            seen_tokens.add(next_token)
            token = next_token
        raise RuntimeError(
            f"{self.config.source} reached max_pages_per_window={self.config.max_pages_per_window} for {start}..{end}; cursor not advanced"
        )

    def fetch_incremental(self, *, watermark=None, now=None):
        observations = []
        cursor = None
        for start, end in self._windows(watermark, now):
            for release in self._fetch_window(start, end):
                normalized = self.normalizer(release, now=now)
                if not normalized:
                    continue
                if isinstance(normalized, dict):
                    normalized = [normalized]
                if not isinstance(normalized, list):
                    raise RuntimeError(f"{self.config.source} normalizer returned unsupported type")
                for item in normalized:
                    if isinstance(item, dict) and item.get("external_id"):
                        observations.append(item)
            cursor = OCDSOpaqueWindowCursor(end.isoformat()).encode()
        return observations, cursor
