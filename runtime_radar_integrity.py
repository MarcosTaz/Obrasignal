"""Runtime integrity guards for the production Radar ingestion boundary.

These guards are deliberately additive. They repair two legacy behaviours without
forking the source clients: multi-lot TED deadlines are collapsed to one valid
calendar deadline for procedure-level actionability, and the TED publication
cursor is staged until the enclosing sync has persisted successfully.
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
    # Deduplicate while retaining deterministic order before max().
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
                # The enclosing sync wrapper discards staged state on any legacy
                # persistence failure and commits it only after the tender write
                # transaction has succeeded.
                stage_source_sync("TED", [], watermark)
                return None
            return original_set_cursor(conn, source, watermark, commit=commit)

        set_source_cursor_after_persistence._obrasignal_ted_cursor_guard = True
        set_source_cursor_after_persistence._obrasignal_original = original_set_cursor
        preload_module.set_source_cursor = set_source_cursor_after_persistence

    return {
        "normalize_ted": app_module.normalize_ted,
        "set_source_cursor": preload_module.set_source_cursor,
    }
