"""Bounded incremental orchestration for Austria's distributed Kerndaten feed.

The core parser/transport lives in ``austria_kerndaten``.  This layer solves a
separate operational problem proven against the live source: a single Austrian
KDQ can contain more recent publications than it is safe to hydrate in one run.

Rules enforced here:
- each synchronization cycle freezes one global ``through`` horizon;
- KDQ items are ordered deterministically by ``(lastmod, item_id)``;
- notice hydration is capped across the whole run, not merely per publisher;
- partial catch-up state is persisted in the cursor and resumes without skips;
- no commercial/lifecycle observations are emitted while any frozen KDQ still
  has backlog; only the final reconciled snapshot becomes visible;
- legacy v1 cursors remain readable and are upgraded to v2 on the next write.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json

from austria_kerndaten import (
    SOURCE,
    AustriaKerndatenConnector as _TransportConnector,
    _deadline_status,
    _legacy_alias_index,
    _merge_state,
    _observation,
    _parse_notice,
    _parse_source_datetime,
    _reanchor_legacy_state,
    _utc,
)


@dataclass
class AustriaKerndatenIncrementalCursor:
    observed_through: str
    datasets: dict
    kdq_observed: dict
    tracked: dict
    catchup: dict

    @classmethod
    def empty(cls):
        return cls(observed_through="", datasets={}, kdq_observed={}, tracked={}, catchup={})

    @classmethod
    def decode(cls, value):
        if value in (None, ""):
            return cls.empty()
        try:
            payload = json.loads(value)
        except Exception as exc:
            raise RuntimeError(f"invalid {SOURCE} cursor; cursor not advanced") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"invalid {SOURCE} cursor; cursor not advanced")
        try:
            version = int(payload.get("version") or 1)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"invalid {SOURCE} cursor version; cursor not advanced") from exc
        if version not in {1, 2}:
            raise RuntimeError(f"invalid {SOURCE} cursor version; cursor not advanced")

        datasets = payload.get("datasets") or {}
        kdq_observed = payload.get("kdq_observed") or {}
        tracked = payload.get("tracked") or {}
        catchup = payload.get("catchup") or {} if version == 2 else {}
        if not all(isinstance(value, dict) for value in (datasets, kdq_observed, tracked, catchup)):
            raise RuntimeError(f"invalid {SOURCE} cursor structure; cursor not advanced")
        return cls(
            observed_through=str(payload.get("observed_through") or ""),
            datasets=deepcopy(datasets),
            kdq_observed=deepcopy(kdq_observed),
            tracked=deepcopy(tracked),
            catchup=deepcopy(catchup),
        )

    def encode(self):
        return json.dumps(
            {
                "version": 2,
                "observed_through": self.observed_through,
                "datasets": self.datasets,
                "kdq_observed": self.kdq_observed,
                "tracked": self.tracked,
                "catchup": self.catchup,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


def _item_key(item):
    modified = _parse_source_datetime(item.get("lastmod"))
    if modified is None:
        raise RuntimeError(f"{SOURCE} KDQ item has invalid lastmod; cursor not advanced")
    return modified, str(item.get("id") or "")


def _checkpoint_key(progress):
    if not isinstance(progress, dict):
        return None
    modified = _parse_source_datetime(progress.get("after_lastmod"))
    item_id = str(progress.get("after_item_id") or "")
    if modified is None or not item_id:
        return None
    return modified, item_id


def _reconcile(*, baseline, pending, now):
    """Turn one complete frozen snapshot into user-visible observations/state."""
    tracked = deepcopy(baseline)
    observations = []
    all_keys = set(tracked) | set(pending)
    for key in sorted(all_keys):
        previous = tracked.get(key)
        incoming = pending.get(key)
        if incoming is not None:
            incoming = _merge_state(previous, incoming)
            actionable, reason = _deadline_status(incoming, now)
            if actionable:
                incoming["was_visible"] = True
                changed = previous != incoming
                tracked[key] = incoming
                if changed or previous is None:
                    observations.append(
                        _observation(
                            incoming,
                            actionable=True,
                            lifecycle_status="open",
                            lifecycle_reason="future_submission_deadline",
                        )
                    )
                continue

            if previous and previous.get("was_visible"):
                incoming["was_visible"] = True
                if reason in {"deadline_missing", "deadline_invalid"}:
                    tracked[key] = incoming
                else:
                    tracked.pop(key, None)
                observations.append(
                    _observation(
                        incoming,
                        actionable=False,
                        lifecycle_status=reason,
                        lifecycle_reason=reason,
                        lifecycle_only=True,
                    )
                )
            else:
                tracked.pop(key, None)
            continue

        if previous is None:
            continue
        actionable, reason = _deadline_status(previous, now)
        if actionable:
            continue
        if previous.get("was_visible"):
            observations.append(
                _observation(
                    previous,
                    actionable=False,
                    lifecycle_status=reason,
                    lifecycle_reason=reason,
                    lifecycle_only=True,
                )
            )
        if reason in {"deadline_missing", "deadline_invalid"}:
            tracked[key] = previous
        else:
            tracked.pop(key, None)

    return observations, {key: value for key, value in tracked.items() if isinstance(value, dict)}


class AustriaKerndatenIncrementalConnector(_TransportConnector):
    """Production incremental connector with bounded, resumable catch-up."""

    def __init__(self, *, max_notice_fetches_per_run=500, **kwargs):
        super().__init__(**kwargs)
        self.max_notice_fetches_per_run = int(max_notice_fetches_per_run)
        if self.max_notice_fetches_per_run < 1:
            raise ValueError("max_notice_fetches_per_run must be >= 1")

    def _new_catchup(self, cursor, *, datasets, now):
        through = _utc(now)
        kdqs = {}
        for dataset_id in sorted(datasets):
            entry = datasets.get(dataset_id) or {}
            for kdq_url in sorted(entry.get("urls") or []):
                observed = _parse_source_datetime(cursor.kdq_observed.get(kdq_url))
                start = (
                    observed - timedelta(hours=self.overlap_hours)
                    if observed is not None
                    else now - timedelta(days=self.initial_lookback_days)
                )
                kdqs[kdq_url] = {
                    "dataset_id": str(dataset_id),
                    "from": _utc(start),
                    "after_lastmod": "",
                    "after_item_id": "",
                    "done": False,
                }
        if not kdqs:
            raise RuntimeError(f"{SOURCE} discovered no KDQ URLs; cursor not advanced")
        return {
            "through": through,
            "datasets": deepcopy(datasets),
            "kdqs": kdqs,
            # Baseline states are copied so unchanged visible opportunities and
            # deadline-only lifecycle transitions survive a multi-run catch-up.
            "pending": deepcopy(cursor.tracked),
        }

    def _validated_catchup(self, catchup, *, now):
        if not isinstance(catchup, dict):
            raise RuntimeError(f"invalid {SOURCE} catchup cursor; cursor not advanced")
        through = _parse_source_datetime(catchup.get("through"))
        datasets = catchup.get("datasets") or {}
        kdqs = catchup.get("kdqs") or {}
        pending = catchup.get("pending") or {}
        if through is None or through > now + timedelta(minutes=5):
            raise RuntimeError(f"invalid {SOURCE} catchup horizon; cursor not advanced")
        if not all(isinstance(value, dict) for value in (datasets, kdqs, pending)):
            raise RuntimeError(f"invalid {SOURCE} catchup structure; cursor not advanced")
        if not kdqs:
            raise RuntimeError(f"invalid {SOURCE} empty catchup; cursor not advanced")
        return through, datasets, kdqs, pending

    def fetch_incremental(self, *, watermark=None, now=None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now = now.astimezone(timezone.utc)

        cursor = AustriaKerndatenIncrementalCursor.decode(watermark)
        observed = _parse_source_datetime(cursor.observed_through)
        if observed is not None and observed > now + timedelta(minutes=5):
            raise RuntimeError(f"{SOURCE} cursor is in the future; cursor not advanced")

        if cursor.catchup:
            catchup = deepcopy(cursor.catchup)
        else:
            datasets = self._discover(cursor)
            catchup = self._new_catchup(cursor, datasets=datasets, now=now)

        through, frozen_datasets, kdq_progress, pending = self._validated_catchup(catchup, now=now)
        kdq_observed = deepcopy(cursor.kdq_observed)
        budget = self.max_notice_fetches_per_run
        successful_scans = 0
        progressed = 0
        completed = 0
        errors = []

        for kdq_url in sorted(kdq_progress):
            progress = kdq_progress[kdq_url]
            if not isinstance(progress, dict):
                raise RuntimeError(f"invalid {SOURCE} KDQ catchup state; cursor not advanced")
            if progress.get("done"):
                continue
            if budget <= 0:
                break

            dataset_id = str(progress.get("dataset_id") or "")
            start = _parse_source_datetime(progress.get("from"))
            if not dataset_id or start is None:
                raise RuntimeError(f"invalid {SOURCE} KDQ catchup bounds; cursor not advanced")
            checkpoint = _checkpoint_key(progress)

            try:
                items = self._kdq_items(kdq_url)
                selected = []
                for item in items:
                    key = _item_key(item)
                    if key[0] < start or key[0] > through:
                        continue
                    if checkpoint is not None and key <= checkpoint:
                        continue
                    selected.append((key, item))
                selected.sort(key=lambda pair: pair[0])
                successful_scans += 1

                batch = selected[:budget]
                item_failed = False
                for key, item in batch:
                    try:
                        payload = self._notice_payload(item["url"])
                        states = _parse_notice(
                            payload,
                            dataset_id=dataset_id,
                            item_id=item["id"],
                            item_lastmod=item["lastmod"],
                            notice_url=item["url"],
                        )
                        alias_index = _legacy_alias_index(pending)
                        for state in states:
                            state = _reanchor_legacy_state(
                                state,
                                alias_index=alias_index,
                                tracked=pending,
                            )
                            state_key = state["external_id"]
                            pending[state_key] = _merge_state(pending.get(state_key), state)
                            # Later aliases in this same run may need to anchor to
                            # the state just discovered, so refresh the index.
                            alias_index = _legacy_alias_index(pending)
                        progress["after_lastmod"] = _utc(key[0])
                        progress["after_item_id"] = key[1]
                        budget -= 1
                        progressed += 1
                    except Exception as exc:
                        errors.append(f"{kdq_url} item {item.get('id')}: {type(exc).__name__}: {str(exc)}")
                        item_failed = True
                        break

                if not item_failed and len(selected) <= len(batch):
                    progress["done"] = True
                    kdq_observed[kdq_url] = _utc(through)
                    completed += 1
            except Exception as exc:
                errors.append(f"{kdq_url}: {type(exc).__name__}: {str(exc)}")
                continue

        catchup["kdqs"] = kdq_progress
        catchup["pending"] = pending
        incomplete = [url for url, state in kdq_progress.items() if not (state or {}).get("done")]

        if incomplete:
            # If the only remaining work is blocked and this run made no forward
            # progress, surface the failure instead of reporting a false success.
            if progressed == 0 and completed == 0 and errors:
                detail = "; ".join(errors[-3:])
                raise RuntimeError(f"{SOURCE} catchup made no progress; cursor not advanced: {detail}")
            next_cursor = AustriaKerndatenIncrementalCursor(
                observed_through=cursor.observed_through,
                datasets=deepcopy(frozen_datasets),
                kdq_observed=kdq_observed,
                tracked=deepcopy(cursor.tracked),
                catchup=catchup,
            )
            # Critical invariant: never expose a partial national snapshot.
            return [], next_cursor.encode()

        observations, tracked = _reconcile(
            baseline=cursor.tracked,
            pending=pending,
            now=now,
        )
        next_cursor = AustriaKerndatenIncrementalCursor(
            observed_through=_utc(through),
            datasets=deepcopy(frozen_datasets),
            kdq_observed=kdq_observed,
            tracked=tracked,
            catchup={},
        )
        return observations, next_cursor.encode()


def fetch_austria_kerndaten_tenders(*, watermark=None, session=None, now=None):
    connector = AustriaKerndatenIncrementalConnector(session=session)
    return connector.fetch_incremental(watermark=watermark, now=now)
