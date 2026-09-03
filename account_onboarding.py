"""First-value bootstrap for newly configured accounts.

A new account should not have to wait for the next source poll before the
Radar can show matches. This module performs a deliberately small,
account-scoped classification pass after the company profile is saved.
The normal ingestion/decision pipeline continues coverage afterwards; profile
writes must never be held hostage by a full-corpus reclassification.
"""
from __future__ import annotations

import re
import unicodedata

from app import db
from company_profile import load_profile
from decision_log import ensure_decision_table
from funnel_integration import persist_and_classify
from notification_events import event_key_for
from opportunity_lifecycle import actionable_predicate, ensure_lifecycle_table
from opportunity_match_pipeline import evaluate_row

# This runs inside POST /profile. Keep it a first-value sample, not a batch job.
# 250 scored rows exceeded the real 30 s production contract. The two-stage
# query below retrieves cheaply in SQL but never evaluates more than 120 rows.
MAX_BOOTSTRAP_ROWS = 50
MAX_BOOTSTRAP_CANDIDATES = 120
BOOTSTRAP_COMMIT_BATCH = 25

# A customer starts with "Apenas oportunidades abertas" enabled. Therefore the
# bounded first-value sample must prefer tenders whose deadline is explicitly
# still open. Unknown-deadline tenders remain eligible because the lifecycle
# model treats missing time evidence as UNKNOWN rather than CLOSED.
CONFIRMED_OPEN_SQL = """t.deadline IS NOT NULL AND TRIM(t.deadline)<>'' AND (
    (LENGTH(TRIM(t.deadline))=10 AND date(t.deadline)>=date('now')) OR
    (LENGTH(TRIM(t.deadline))<>10 AND datetime(t.deadline)>=datetime('now'))
)"""

_DECISION_ORDER = {"QUALIFIED": 0, "REVIEW": 1, "REJECT": 2}
_STOPWORDS = {
    "para", "com", "sem", "das", "dos", "uma", "uns", "nas", "nos",
    "de", "da", "do", "em", "por", "serviços", "servicos", "trabalhos",
    "trabalho", "empresa", "empresas", "contratos", "contrato",
}


def _bootstrap_rank(pair):
    """Put the account's strongest matches ahead of generic source ranking."""
    item, evaluation = pair
    return (
        _DECISION_ORDER.get(str(evaluation.get("decision") or "REJECT"), 3),
        -int(evaluation.get("profile_score") or 0),
        -int(evaluation.get("lot_score") or 0),
        -int(item.get("score") or 0),
        str(item.get("external_id") or item.get("id") or ""),
    )


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _profile_text_hints(profile: dict) -> list[str]:
    """Return a few discriminative words for SQL candidate discovery.

    This stage is recall-only. The actual commercial decision is still made by
    ``evaluate_row``. Hints merely stop the generic source score from deciding
    which 80 rows an electrician/cleaner/software supplier is ever allowed to
    be evaluated against.
    """
    values = [profile.get("activity")]
    values.extend(profile.get("contract_interests") or [])
    values.extend(profile.get("services") or [])
    values.extend(profile.get("capability_tags") or [])
    tokens = []
    for value in values:
        for token in re.findall(r"[A-Za-zÀ-ÿ0-9]+", str(value or "")):
            folded = _fold(token).strip()
            if len(folded) < 5 or folded in _STOPWORDS:
                continue
            # SQLite lower() is not a full Unicode case-folder. Keep original
            # text hints conservative and let CPV hints cover known trades.
            if token not in tokens:
                tokens.append(token)
            if len(tokens) >= 8:
                return tokens
    return tokens


def _hint_clause(profile: dict):
    clauses = []
    params = []
    # Specific CPV prefixes are high-value discovery evidence. Broad divisions
    # are allowed too, but only as one signal among text hints and never as the
    # final decision.
    for prefix in [str(v).strip() for v in (profile.get("cpv_prefixes") or []) if str(v).strip()][:8]:
        clauses.append("REPLACE(COALESCE(t.cpv,''),' ','') LIKE ?")
        params.append(prefix + "%")
    searchable = "LOWER(COALESCE(t.title,'') || ' ' || COALESCE(t.description,''))"
    for token in _profile_text_hints(profile):
        clauses.append(f"{searchable} LIKE LOWER(?)")
        params.append("%" + token + "%")
    return clauses, params


def _emit_bootstrap_events(conn, account_id: str) -> int:
    ensure_lifecycle_table(conn)
    rows = conn.execute(
        f"""SELECT t.*, d.score AS account_score
           FROM tenders t
           JOIN (
               SELECT od.source, od.external_id, MAX(od.id) AS max_id
               FROM opportunity_decisions od
               WHERE od.account_id=?
               GROUP BY od.source, od.external_id
           ) latest ON latest.source=t.source AND latest.external_id=t.external_id
           JOIN opportunity_decisions d ON d.id=latest.max_id
           LEFT JOIN opportunity_lifecycle lc
             ON lc.source=t.source AND lc.external_id=t.external_id
           WHERE d.decision='QUALIFIED'
             AND d.score >= 75
             AND {actionable_predicate('lc', 't')}
           ORDER BY d.score DESC, COALESCE(NULLIF(t.publication_date,''), t.first_seen) DESC
           LIMIT ?""",
        (account_id, MAX_BOOTSTRAP_ROWS),
    ).fetchall()
    created = 0
    for row in rows:
        item = dict(row)
        event_key = event_key_for(account_id, item)
        cur = conn.execute(
            """INSERT OR IGNORE INTO opportunity_events
               (account_id,event_key,tender_id,source,event_type,score,created_at)
               VALUES (?,?,?,?,?,?,datetime('now'))""",
            (account_id, event_key, item.get('id'), item.get('source'), 'new_high_match', item.get('account_score', 0)),
        )
        created += int(cur.rowcount or 0)
    conn.commit()
    return created


def _candidate_rows(conn, profile: dict, countries: list[str], candidate_limit: int):
    base_where = [actionable_predicate('lc', 't')]
    base_params = []
    if countries:
        placeholders = ",".join("?" for _ in countries)
        base_where.append(f"UPPER(COALESCE(t.country,'')) IN ({placeholders})")
        base_params.extend(countries)

    order = (
        f"ORDER BY CASE WHEN {CONFIRMED_OPEN_SQL} THEN 0 ELSE 1 END, "
        "COALESCE(NULLIF(t.publication_date,''), t.first_seen) DESC, "
        "COALESCE(t.score,0) DESC"
    )
    from_sql = """FROM tenders t
        LEFT JOIN opportunity_lifecycle lc
          ON lc.source=t.source AND lc.external_id=t.external_id"""

    # Profile-hinted candidates are deliberately queried first. This is the
    # missing link that previously let a metal/works generic score consume the
    # entire bounded sample before a specialist's own criteria were evaluated.
    hint_clauses, hint_params = _hint_clause(profile)
    hinted = []
    if hint_clauses:
        hint_limit = min(candidate_limit, max(MAX_BOOTSTRAP_ROWS, candidate_limit // 2))
        hinted = conn.execute(
            f"SELECT t.* {from_sql} WHERE {' AND '.join(base_where)} "
            f"AND ({' OR '.join(hint_clauses)}) {order} LIMIT ?",
            (*base_params, *hint_params, hint_limit),
        ).fetchall()

    # Fill remaining discovery capacity with the freshest/openest generic work.
    # Deduplication happens in Python so hinted candidates never lose priority.
    generic = conn.execute(
        f"SELECT t.* {from_sql} WHERE {' AND '.join(base_where)} {order} LIMIT ?",
        (*base_params, candidate_limit),
    ).fetchall()

    merged = []
    seen = set()
    for row in [*hinted, *generic]:
        key = (str(row["source"]), str(row["external_id"]))
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
        if len(merged) >= candidate_limit:
            break
    return merged


def bootstrap_account(account_id: str, limit: int = MAX_BOOTSTRAP_ROWS) -> int:
    """Classify a bounded, profile-directed first-value sample for one account."""
    account_id = str(account_id or "").strip()
    if not account_id:
        return 0
    conn = db()
    try:
        ensure_lifecycle_table(conn)
        ensure_decision_table(conn)
        profile = load_profile(account_id)
        countries = [str(value).strip().upper() for value in (profile.get("countries") or []) if str(value).strip()]
        requested_limit = max(1, min(int(limit), MAX_BOOTSTRAP_ROWS))
        candidate_limit = min(MAX_BOOTSTRAP_CANDIDATES, max(requested_limit, requested_limit * 2))
        rows = _candidate_rows(conn, profile, countries, candidate_limit)

        prepared = []
        for row in rows:
            item = dict(row)
            prepared.append((item, evaluate_row(item, profile=profile)))

        # Source ordering is only candidate discovery. Final first-value
        # selection is explicitly account-specific.
        prepared.sort(key=_bootstrap_rank)
        selected = prepared[:requested_limit]

        for index, (item, evaluation) in enumerate(selected, start=1):
            persist_and_classify(
                conn,
                item,
                False,
                account_id=account_id,
                profile=profile,
                evaluation=evaluation,
                commit=False,
                ensure=False,
            )
            if index % BOOTSTRAP_COMMIT_BATCH == 0:
                conn.commit()
        if selected and len(selected) % BOOTSTRAP_COMMIT_BATCH:
            conn.commit()

        _emit_bootstrap_events(conn, account_id)
        return len(selected)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
