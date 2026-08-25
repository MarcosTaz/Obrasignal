"""Saved Search / Search Profiles v0.

This module stores reusable search intent. It deliberately does not own a second
search engine: ``query_opportunities`` is the canonical query path shared by
saved profiles and the HTTP opportunity search facade.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import uuid

from opportunity_lifecycle import ensure_lifecycle_table

FILTER_SCHEMA_VERSION = 1
CANONICAL_SORT = "score_desc_deadline_asc"
SUPPORTED_SORTS = frozenset({CANONICAL_SORT})
SUPPORTED_FILTERS = frozenset({"market", "country", "q", "source", "open", "minscore"})
SUPPORTED_MARKETS = frozenset({"PT", "EU", "ALL"})
PROFILE_STATUSES = frozenset({"ACTIVE", "INVALID"})
MAX_NAME_LENGTH = 120
MAX_QUERY_LENGTH = 240
MAX_FILTER_JSON_BYTES = 4096
_SOURCE_RE = re.compile(r"^[A-Z0-9_.-]{1,64}$")
_COUNTRY_RE = re.compile(r"^[A-Z]{3}$")


class SearchProfileError(ValueError):
    code = "invalid_search_profile"


class SearchProfileNotFound(SearchProfileError):
    code = "not_found"


class SearchProfileNeedsUpdate(SearchProfileError):
    code = "search_profile_needs_update"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_search_profile_table(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS search_profiles(
            profile_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            name TEXT NOT NULL,
            filters_json TEXT NOT NULL,
            sort TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_run_at TEXT,
            is_default INTEGER NOT NULL DEFAULT 0 CHECK(is_default IN (0,1)),
            status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','INVALID')),
            filter_schema_version INTEGER NOT NULL
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_profiles_account ON search_profiles(account_id, updated_at DESC)"
    )
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_search_profiles_one_default
           ON search_profiles(account_id) WHERE is_default=1"""
    )


def validate_name(name) -> str:
    if not isinstance(name, str):
        raise SearchProfileError("name must be a string")
    value = name.strip()
    if not value:
        raise SearchProfileError("name is required")
    if len(value) > MAX_NAME_LENGTH:
        raise SearchProfileError(f"name must be at most {MAX_NAME_LENGTH} characters")
    if any(ord(ch) < 32 for ch in value):
        raise SearchProfileError("name contains control characters")
    return value


def validate_sort(sort) -> str:
    value = CANONICAL_SORT if sort in (None, "") else str(sort).strip()
    if value not in SUPPORTED_SORTS:
        raise SearchProfileError("unsupported sort mode")
    return value


def normalize_filters(filters, *, defaults: bool = True) -> dict:
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        raise SearchProfileError("filters must be an object")
    unknown = set(filters) - SUPPORTED_FILTERS
    if unknown:
        raise SearchProfileError("unsupported filters: " + ", ".join(sorted(unknown)))

    result = {}
    market = filters.get("market", "PT" if defaults else None)
    if market not in (None, ""):
        if not isinstance(market, str):
            raise SearchProfileError("market must be a string")
        market = market.strip().upper()
        if market not in SUPPORTED_MARKETS:
            raise SearchProfileError("unsupported market")
        result["market"] = market

    country = filters.get("country")
    if country not in (None, ""):
        if not isinstance(country, str):
            raise SearchProfileError("country must be a string")
        country = country.strip().upper()
        if not _COUNTRY_RE.fullmatch(country):
            raise SearchProfileError("country must be an ISO-3 code")
        result["country"] = country

    query = filters.get("q")
    if query not in (None, ""):
        if not isinstance(query, str):
            raise SearchProfileError("q must be a string")
        query = query.strip().lower()
        if len(query) > MAX_QUERY_LENGTH:
            raise SearchProfileError(f"q must be at most {MAX_QUERY_LENGTH} characters")
        if query:
            result["q"] = query

    source = filters.get("source")
    if source not in (None, ""):
        if not isinstance(source, str):
            raise SearchProfileError("source must be a string")
        source = source.strip().upper()
        if not _SOURCE_RE.fullmatch(source):
            raise SearchProfileError("invalid source")
        result["source"] = source

    if "open" in filters:
        open_only = filters["open"]
        if not isinstance(open_only, bool):
            raise SearchProfileError("open must be a boolean")
        result["open"] = open_only

    if "minscore" in filters and filters["minscore"] not in (None, ""):
        value = filters["minscore"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise SearchProfileError("minscore must be an integer")
        if not 0 <= value <= 100:
            raise SearchProfileError("minscore must be between 0 and 100")
        result["minscore"] = value

    encoded = json.dumps(result, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(encoded) > MAX_FILTER_JSON_BYTES:
        raise SearchProfileError("filters payload is too large")
    return result


def parse_query_filters(args) -> tuple[dict, int, str]:
    """Translate the existing HTTP query contract into the canonical contract."""
    raw = {}
    for key in ("market", "country", "q", "source"):
        value = args.get(key)
        if value not in (None, ""):
            raw[key] = value
    if args.get("open") not in (None, ""):
        text = str(args.get("open")).strip().lower()
        if text not in {"0", "1", "false", "true", "no", "yes"}:
            raise SearchProfileError("open must be boolean")
        raw["open"] = text in {"1", "true", "yes"}
    if args.get("minscore") not in (None, ""):
        try:
            raw["minscore"] = int(args.get("minscore"))
        except (TypeError, ValueError) as exc:
            raise SearchProfileError("minscore must be an integer") from exc
    try:
        limit = int(args.get("limit", 20) or 20)
    except (TypeError, ValueError) as exc:
        raise SearchProfileError("limit must be an integer") from exc
    if not 1 <= limit <= 100:
        raise SearchProfileError("limit must be between 1 and 100")
    sort = validate_sort(args.get("sort"))
    return normalize_filters(raw), limit, sort


def query_opportunities(conn, account_id: str, filters: dict, *, limit: int = 20, sort: str = CANONICAL_SORT):
    """Execute the one canonical v0 opportunity-search query.

    All SQL values are bound parameters. Sort is an enum translated to a fixed
    SQL clause; arbitrary database columns or expressions never enter SQL.
    """
    normalized = normalize_filters(filters)
    validate_sort(sort)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise SearchProfileError("limit must be between 1 and 100")

    ensure_lifecycle_table(conn)
    where = ["COALESCE(lc.is_actionable,1)=1"]
    params = []
    market = normalized.get("market", "PT")
    if market in ("PT", "EU"):
        where.append("(t.market=? OR (t.market IS NULL AND t.country=?))")
        # Preserve the existing search semantics exactly, including the legacy
        # PT fallback used by the EU view.
        params.extend([market, "PRT"])
    if normalized.get("country"):
        where.append("t.country=?")
        params.append(normalized["country"])
    if normalized.get("q"):
        where.append("LOWER(COALESCE(t.title,'') || ' ' || COALESCE(t.description,'') || ' ' || COALESCE(t.buyer,'') || ' ' || COALESCE(t.cpv,'')) LIKE ?")
        params.append(f"%{normalized['q']}%")
    if normalized.get("source"):
        where.append("UPPER(t.source)=?")
        params.append(normalized["source"])
    if normalized.get("open"):
        where.append("t.deadline IS NOT NULL AND t.deadline<>'' AND datetime(t.deadline)>=datetime('now')")
    if normalized.get("minscore") is not None:
        where.append("COALESCE(d.score,t.score)>=?")
        params.append(normalized["minscore"])

    return conn.execute(
        f"""SELECT t.*, COALESCE(lc.is_actionable,1) AS is_actionable,
                   lc.lifecycle_status, lc.lifecycle_reason,
                   lc.source_updated_at AS lifecycle_source_updated_at,
                   lc.last_observed AS lifecycle_last_observed
            FROM tenders t
            LEFT JOIN opportunity_lifecycle lc ON lc.source=t.source AND lc.external_id=t.external_id
            LEFT JOIN (SELECT source, external_id, MAX(id) max_id FROM opportunity_decisions WHERE account_id=? GROUP BY source, external_id) latest
              ON latest.source=t.source AND latest.external_id=t.external_id
            LEFT JOIN opportunity_decisions d ON d.id=latest.max_id
            WHERE {' AND '.join(where)}
            ORDER BY COALESCE(d.score,t.score) DESC, t.deadline ASC LIMIT ?""",
        (account_id, *params, limit),
    ).fetchall()


def _decode_row(row) -> dict:
    item = dict(row)
    item["filters"] = json.loads(item.pop("filters_json"))
    item["is_default"] = bool(item["is_default"])
    return item


def _mark_invalid(conn, profile_id: str, account_id: str) -> None:
    conn.execute(
        "UPDATE search_profiles SET status='INVALID', updated_at=? WHERE profile_id=? AND account_id=?",
        (_now(), profile_id, account_id),
    )
    conn.commit()


def _validated_row(conn, row, account_id: str, *, require_runnable: bool = False) -> dict:
    if row is None:
        raise SearchProfileNotFound("search profile not found")
    item = _decode_row(row)
    try:
        if item["filter_schema_version"] != FILTER_SCHEMA_VERSION:
            raise SearchProfileNeedsUpdate("filter schema version is no longer supported")
        item["filters"] = normalize_filters(item["filters"])
        item["sort"] = validate_sort(item["sort"])
    except SearchProfileError as exc:
        if item["status"] != "INVALID":
            _mark_invalid(conn, item["profile_id"], account_id)
            item["status"] = "INVALID"
        if require_runnable:
            raise SearchProfileNeedsUpdate(str(exc)) from exc
    if require_runnable and item["status"] != "ACTIVE":
        raise SearchProfileNeedsUpdate("search profile requires update")
    return item


def list_search_profiles(conn, account_id: str) -> list[dict]:
    ensure_search_profile_table(conn)
    rows = conn.execute(
        "SELECT * FROM search_profiles WHERE account_id=? ORDER BY is_default DESC, updated_at DESC, profile_id",
        (account_id,),
    ).fetchall()
    return [_validated_row(conn, row, account_id) for row in rows]


def get_search_profile(conn, account_id: str, profile_id: str, *, require_runnable: bool = False) -> dict:
    ensure_search_profile_table(conn)
    row = conn.execute(
        "SELECT * FROM search_profiles WHERE profile_id=? AND account_id=?",
        (profile_id, account_id),
    ).fetchone()
    return _validated_row(conn, row, account_id, require_runnable=require_runnable)


def create_search_profile(conn, account_id: str, *, name, filters=None, sort=None, is_default=False) -> dict:
    ensure_search_profile_table(conn)
    name = validate_name(name)
    filters = normalize_filters(filters)
    sort = validate_sort(sort)
    if not isinstance(is_default, bool):
        raise SearchProfileError("is_default must be a boolean")
    now = _now()
    profile_id = uuid.uuid4().hex
    with conn:
        if is_default:
            conn.execute("UPDATE search_profiles SET is_default=0, updated_at=? WHERE account_id=?", (now, account_id))
        conn.execute(
            """INSERT INTO search_profiles(
                   profile_id,account_id,name,filters_json,sort,created_at,updated_at,
                   last_run_at,is_default,status,filter_schema_version
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (profile_id, account_id, name, json.dumps(filters, separators=(",", ":"), sort_keys=True), sort,
             now, now, None, int(is_default), "ACTIVE", FILTER_SCHEMA_VERSION),
        )
    return get_search_profile(conn, account_id, profile_id)


def update_search_profile(conn, account_id: str, profile_id: str, changes: dict) -> dict:
    ensure_search_profile_table(conn)
    if not isinstance(changes, dict):
        raise SearchProfileError("payload must be an object")
    allowed = {"name", "filters", "sort", "is_default"}
    unknown = set(changes) - allowed
    if unknown:
        raise SearchProfileError("unsupported fields: " + ", ".join(sorted(unknown)))
    current = get_search_profile(conn, account_id, profile_id)
    name = validate_name(changes.get("name", current["name"]))
    filters = normalize_filters(changes.get("filters", current["filters"]))
    sort = validate_sort(changes.get("sort", current["sort"]))
    is_default = changes.get("is_default", current["is_default"])
    if not isinstance(is_default, bool):
        raise SearchProfileError("is_default must be a boolean")
    now = _now()
    with conn:
        if is_default:
            conn.execute(
                "UPDATE search_profiles SET is_default=0, updated_at=? WHERE account_id=? AND profile_id<>?",
                (now, account_id, profile_id),
            )
        conn.execute(
            """UPDATE search_profiles
               SET name=?, filters_json=?, sort=?, updated_at=?, is_default=?, status='ACTIVE', filter_schema_version=?
               WHERE profile_id=? AND account_id=?""",
            (name, json.dumps(filters, separators=(",", ":"), sort_keys=True), sort, now, int(is_default),
             FILTER_SCHEMA_VERSION, profile_id, account_id),
        )
    return get_search_profile(conn, account_id, profile_id)


def delete_search_profile(conn, account_id: str, profile_id: str) -> None:
    ensure_search_profile_table(conn)
    with conn:
        cur = conn.execute(
            "DELETE FROM search_profiles WHERE profile_id=? AND account_id=?",
            (profile_id, account_id),
        )
    if not cur.rowcount:
        raise SearchProfileNotFound("search profile not found")


def run_search_profile(conn, account_id: str, profile_id: str, *, limit: int = 20):
    profile = get_search_profile(conn, account_id, profile_id, require_runnable=True)
    rows = query_opportunities(conn, account_id, profile["filters"], limit=limit, sort=profile["sort"])
    ran_at = _now()
    with conn:
        conn.execute(
            "UPDATE search_profiles SET last_run_at=?, updated_at=? WHERE profile_id=? AND account_id=?",
            (ran_at, ran_at, profile_id, account_id),
        )
    return profile, rows
