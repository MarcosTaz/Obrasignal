"""Runtime integrity guards for the production Radar boundary.

These guards are deliberately additive. They repair legacy behaviours without
forking the source clients: multi-lot TED deadlines are collapsed to one valid
calendar deadline for procedure-level actionability, the TED publication cursor
is staged until the enclosing sync has persisted successfully, and API deadline
state agrees with the database rule that a date-only deadline remains open for
its entire calendar day.
"""
from __future__ import annotations

import json
import re

from source_runtime import stage_source_sync

_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_COMPACT_DATE_RE = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")


def _date_tokens(value):
    """Extract ISO calendar dates from nested TED field values."""
    if value in (None, "", [], {}):
        return []
    if isinstance(value, dict):
        out = []
        for nested in value.values():
            out.extend(_date_tokens(nested))
        return out
    if isinstance(value, (list, tuple, set)):
        out = []
        for nested in value:
            out.extend(_date_tokens(nested))
        return out

    text = str(value).strip()
    if not text:
        return []
    if text[:1] in "[{":
        try:
            return _date_tokens(json.loads(text))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    out = [f"{y}-{m}-{d}" for y, m, d in _DATE_RE.findall(text)]
    out.extend(f"{y}-{m}-{d}" for y, m, d in _COMPACT_DATE_RE.findall(text))
    return list(dict.fromkeys(out))


def canonical_ted_deadline(notice, fallback=None):
    """Return the latest lot calendar deadline present in one TED notice.

    A procedure remains commercially actionable while at least one represented
    lot is still open. The old generic ``flat`` helper joined lot deadlines with
    `` | ``, producing a string SQLite/Python could not parse as a date and making
    valid notices disappear from the open Radar. Using the latest lot date avoids
    closing the whole notice when only an earlier lot has expired. Lot-level
    ranking remains free to model individual deadlines separately later.
    """
    candidates = []
    if isinstance(notice, dict):
        for key in (
            "deadline-receipt-tender-date-lot",
            "deadline-date-lot",
            "deadlineDate",
        ):
            candidates.extend(_date_tokens(notice.get(key)))
    if candidates:
        return max(candidates)
    fallback_dates = _date_tokens(fallback)
    return max(fallback_dates) if fallback_dates else fallback


def _install_api_deadline_consistency():
    # api has already been imported by cors_app before this runtime installer is
    # invoked. Importing it here therefore patches the live module rather than
    # creating an alternate application object.
    import api as api_module

    original = api_module._deadline_state
    if getattr(original, "_obrasignal_date_only_today_guard", False):
        return original

    def deadline_state(value):
        result = dict(original(value))
        raw = str(value or "").strip()
        # Database open filters deliberately use date(deadline) >= date('now').
        # Preserve that same contract in API/UI: exact time is unknown, but the
        # opportunity is still valid through the stated calendar day.
        if len(raw) == 10 and result.get("days_remaining") == 0 and result.get("state") == "unknown":
            result["state"] = "urgent"
        return result

    deadline_state._obrasignal_date_only_today_guard = True
    deadline_state._obrasignal_original = original
    api_module._deadline_state = deadline_state
    return deadline_state


def install(preload_module, app_module):
    """Install idempotent production guards before the background writer starts."""
    original_normalize = app_module.normalize_ted
    if not getattr(original_normalize, "_obrasignal_radar_integrity", False):
        def normalize_ted(notice):
            item = original_normalize(notice)
            item["deadline"] = canonical_ted_deadline(notice, item.get("deadline"))
            return item

        normalize_ted._obrasignal_radar_integrity = True
        normalize_ted._obrasignal_original = original_normalize
        app_module.normalize_ted = normalize_ted

    original_set_cursor = preload_module.set_source_cursor
    if not getattr(original_set_cursor, "_obrasignal_ted_cursor_guard", False):
        def set_source_cursor_after_persistence(conn, source, watermark, *, commit=True):
            if str(source or "").upper() == "TED":
                stage_source_sync("TED", [], watermark)
                return None
            return original_set_cursor(conn, source, watermark, commit=commit)

        set_source_cursor_after_persistence._obrasignal_ted_cursor_guard = True
        set_source_cursor_after_persistence._obrasignal_original = original_set_cursor
        preload_module.set_source_cursor = set_source_cursor_after_persistence

    deadline_state = _install_api_deadline_consistency()
    return {
        "normalize_ted": app_module.normalize_ted,
        "set_source_cursor": preload_module.set_source_cursor,
        "deadline_state": deadline_state,
    }
