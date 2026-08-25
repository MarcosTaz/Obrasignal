"""Reusable OCDS adapter for APIs that paginate with an opaque cursor link.

The opaque source cursor exists only inside one result window. ObraSignal
persists a temporal high-water mark only after every source page in the window
has completed. Both daily and sub-daily windows are supported so high-frequency
sources do not need to replay an entire publication day on every sync.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
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
    # When window_minutes is configured, the three minute fields replace the
    # day-based window/lookback/overlap values above.
    window_minutes: int | None = None
    initial_lookback_minutes: int = 1440
    overlap_minutes: int = 5
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
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        else:
            stamp = text
        if not stamp:
            return None
        try:
            if "T" in stamp:
                parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    return None
                return cls(stamp)
            return cls(date.fromisoformat(stamp[:10]).isoformat())
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


def _datetime(value):
    """Parse an instant only when its timezone is explicit.

    This helper is used for ObraSignal-owned sub-daily cursor/window instants.
    Date-only cursor values have separate calendar semantics in ``_date``.
    A timezone-naive datetime is temporally ambiguous and must not be promoted
    to UTC merely because this internal representation is stored in UTC.
    """
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min, tzinfo=timezone.utc)
    elif value:
        text = str(value).strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _cursor_stamp(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("subdaily OCDS cursor timestamp must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


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


def _normalized_items(value, *, source):
    if not value:
        return []
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        raise RuntimeError(f"{source} normalizer returned unsupported type")
    return [item for item in value if isinstance(item, dict) and item.get("external_id")]


class OCDSOpaqueCursorAdapter:
    def __init__(self, config, *, params_factory, normalizer=None, window_processor=None, session=None, headers=None):
        self.config = config
        self.params_factory = params_factory
        self.normalizer = normalizer
        self.window_processor = window_processor
        self.session = session or requests.Session()
        self.headers = dict(headers or {})
        if not callable(self.normalizer) and not callable(self.window_processor):
            raise TypeError("opaque-cursor adapter requires a normalizer or window_processor")

    def _subdaily(self):
        return self.config.window_minutes is not None

    def _start_point(self, watermark, now):
        cursor = OCDSOpaqueWindowCursor.decode(watermark)
        if self._subdaily():
            current = _datetime(now or datetime.now(timezone.utc))
            if cursor:
                completed = _datetime(cursor.completed_through)
                if completed:
                    return completed - timedelta(minutes=max(0, int(self.config.overlap_minutes)))
            return current - timedelta(minutes=max(0, int(self.config.initial_lookback_minutes)))

        today = _date(now or datetime.now(timezone.utc))
        if cursor:
            completed = _date(cursor.completed_through)
            if completed:
                return completed + timedelta(days=1) - timedelta(days=max(0, int(self.config.overlap_days)))
        return today - timedelta(days=max(0, int(self.config.initial_lookback_days)))

    def _windows(self, watermark, now):
        count = 0
        maximum = max(1, int(self.config.max_windows_per_sync))
        if self._subdaily():
            end_limit = _datetime(now or datetime.now(timezone.utc))
            start = self._start_point(watermark, end_limit)
            width = timedelta(minutes=max(1, int(self.config.window_minutes)))
            while start < end_limit and count < maximum:
                end = min(end_limit, start + width)
                yield start, end
                start = end
                count += 1
            return

        end_limit = _date(now or datetime.now(timezone.utc))
        start = self._start_point(watermark, end_limit)
        width = max(1, int(self.config.window_days))
        while start <= end_limit and count < maximum:
            end = min(end_limit, start + timedelta(days=width - 1))
            yield start, end
            start = end + timedelta(days=1)
            count += 1

    def _fetch_window(self, start, end):
        base_params = dict(self.params_factory(start, end) or {})
        base_params[self.config.page_size_param] = str(max(1, int(self.config.page_size)))
        token = None
        seen_tokens = set()
        releases = []
        for _page in range(1, max(1, int(self.config.max_pages_per_window)) + 1):
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

    def _process_window(self, releases, *, start, end, now):
        if callable(self.window_processor):
            value = self.window_processor(releases, start=start, end=end, now=now)
            return _normalized_items(value, source=self.config.source)
        observations = []
        for release in releases:
            value = self.normalizer(release, now=now)
            observations.extend(_normalized_items(value, source=self.config.source))
        return observations

    def fetch_incremental(self, *, watermark=None, now=None):
        observations = []
        cursor = None
        for start, end in self._windows(watermark, now):
            releases = self._fetch_window(start, end)
            observations.extend(self._process_window(releases, start=start, end=end, now=now))
            cursor = OCDSOpaqueWindowCursor(_cursor_stamp(end)).encode()
        return observations, cursor
