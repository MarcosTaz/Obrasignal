"""Keep the legacy ``tenders`` compatibility projection aligned with Signal truth.

Staged global-source records are first written by the legacy sync path and only
then admitted/rejected by ``source_runtime`` publisher-time authority. This module
reconciles that compatibility projection from canonical ``signal_records`` before
Radar/decision consumers run, so a rejected late arrival cannot become customer
truth merely because it reached the legacy transaction first.
"""
from collections.abc import Mapping
import json

from signal_store import get_signal_record, signal_type_of


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _snapshot(canonical):
    raw = canonical.get("normalized_json") if canonical else None
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _identity(record):
    if not isinstance(record, Mapping):
        return None
    source = str(record.get("source") or "").strip()
    external_id = str(record.get("external_id") or "").strip()
    if not source or not external_id:
        return None
    return source, external_id


def reconcile_staged_tender_projection(
    conn,
    staged_items,
    *,
    accepted_tender_identities=(),
    accepted_last_seen=None,
    commercial_score,
    commit=True,
):
    """Project canonical staged TENDER truth back into the legacy table.

    ``accepted_tender_identities`` is the exact set admitted by the just-completed
    source transaction. Accepted rows retain the legacy sync-run ``last_seen`` so
    downstream decisioning sees newly accepted work. Rejected rows are restored
    from canonical Signal truth and use the canonical ``last_observed`` timestamp,
    preventing a stale arrival from masquerading as newly accepted work.

    If a staged TENDER has no canonical Signal record (for example a first-time
    source transaction rolled back), any legacy row created by the earlier legacy
    transaction is removed. This is fail-closed: compatibility data cannot outrun
    canonical source persistence.

    A direct source-runtime unit/integration call with no legacy sync run is not a
    customer-projection event. In that case an accepted canonical Signal may update
    an already-existing compatibility row, but it must not manufacture a new
    ``tenders`` row merely because the compatibility table happens to exist.
    """
    if not _table_exists(conn, "tenders"):
        return {"reconciled": 0, "deleted": 0}

    accepted = {
        (str(source).strip(), str(external_id).strip())
        for source, external_id in accepted_tender_identities
    }
    reconciled = 0
    deleted = 0
    seen = set()

    for item in staged_items or []:
        for record in getattr(item, "records", ()) or ():
            identity = _identity(record)
            if identity is None or identity in seen:
                continue
            seen.add(identity)
            if signal_type_of(record) != "TENDER":
                continue

            source, external_id = identity
            canonical = get_signal_record(conn, source, external_id, "TENDER")
            if canonical is None:
                cur = conn.execute(
                    "DELETE FROM tenders WHERE source=? AND external_id=?",
                    (source, external_id),
                )
                deleted += int(cur.rowcount or 0)
                continue

            existing = conn.execute(
                "SELECT id, first_seen, last_seen FROM tenders WHERE source=? AND external_id=?",
                (source, external_id),
            ).fetchone()
            if identity in accepted and existing is None and not accepted_last_seen:
                # No legacy sync transaction occurred. Canonical source storage is
                # valid, but creating a compatibility row here would widen the
                # source transaction into an unrelated customer-projection write.
                continue

            snapshot = _snapshot(canonical)
            title = canonical.get("title")
            description = canonical.get("description")
            buyer = canonical.get("buyer")
            country = canonical.get("country")
            cpv = snapshot.get("cpv") or canonical.get("category_code")
            value = canonical.get("value")
            deadline = canonical.get("deadline")
            publication_date = canonical.get("publication_date")
            published_at = canonical.get("published_at")
            url = canonical.get("url")
            market = snapshot.get("market")
            score, priority_label, priority_class, match_reason = commercial_score(
                title or "", description or "", cpv or "", deadline
            )

            canonical_seen = canonical.get("last_observed") or canonical.get("first_observed")
            last_seen = (
                accepted_last_seen
                if identity in accepted and accepted_last_seen
                else canonical_seen
            )
            first_seen = (
                existing["first_seen"]
                if existing is not None and existing["first_seen"]
                else canonical.get("first_observed")
            )

            values = (
                title,
                description,
                buyer,
                country,
                cpv,
                value,
                deadline,
                publication_date,
                url,
                score,
                last_seen,
                published_at,
                match_reason,
                priority_label,
                priority_class,
                market,
            )
            if existing is not None:
                conn.execute(
                    """UPDATE tenders SET
                        title=?,description=?,buyer=?,country=?,cpv=?,value=?,deadline=?,
                        publication_date=?,url=?,score=?,last_seen=?,published_at=?,
                        match_reason=?,priority_label=?,priority_class=?,market=?
                        WHERE id=?""",
                    values + (existing["id"],),
                )
            else:
                conn.execute(
                    """INSERT INTO tenders(
                        title,description,buyer,country,cpv,value,deadline,publication_date,
                        url,score,last_seen,published_at,match_reason,priority_label,
                        priority_class,market,source,external_id,first_seen
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    values + (source, external_id, first_seen),
                )
            reconciled += 1

    if commit:
        conn.commit()
    return {"reconciled": reconciled, "deleted": deleted}
