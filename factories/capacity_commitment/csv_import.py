from __future__ import annotations

import csv
import hashlib
import io
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .evidence import (
    EvidenceSource,
    ExtractedFact,
    FactType,
    ReviewState,
    validate_fact,
    validate_source,
)


MAX_CSV_BYTES = 750_000
MAX_CSV_ROWS = 5_000
CSV_FIELDS = (
    "fact_id",
    "fact_type",
    "raw_value",
    "normalized_value",
    "scope_ref",
    "page_ref",
    "clause_ref",
)


@dataclass(frozen=True)
class CsvEvidencePreview:
    sha256: str
    row_count: int
    facts: tuple[ExtractedFact, ...]


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def preview_csv_facts(
    content: bytes,
    *,
    tenant_id: str,
    evidence_id: str,
) -> CsvEvidencePreview:
    if not isinstance(content, bytes):
        raise ValueError("CSV content must be bytes")
    if not content:
        raise ValueError("CSV content is empty")
    if len(content) > MAX_CSV_BYTES:
        raise ValueError("CSV content exceeds maximum size")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8") from exc
    if "\x00" in text:
        raise ValueError("CSV contains NUL")

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise ValueError("CSV header is required")
    fieldnames = tuple(name.strip() for name in reader.fieldnames)
    if fieldnames != CSV_FIELDS:
        raise ValueError(f"CSV header must exactly match {list(CSV_FIELDS)}")

    facts = []
    seen_ids = set()
    for index, row in enumerate(reader, start=2):
        if len(facts) >= MAX_CSV_ROWS:
            raise ValueError("CSV row limit exceeded")
        if None in row:
            raise ValueError(f"CSV row {index} has unexpected extra columns")
        try:
            fact_type = FactType((row["fact_type"] or "").strip())
        except ValueError as exc:
            raise ValueError(f"CSV row {index} has invalid fact_type") from exc
        fact = validate_fact(
            ExtractedFact(
                tenant_id=tenant_id,
                fact_id=(row["fact_id"] or "").strip(),
                evidence_id=evidence_id,
                fact_type=fact_type,
                raw_value=row["raw_value"] or "",
                normalized_value=row["normalized_value"] or "",
                scope_ref=_optional(row["scope_ref"]),
                page_ref=_optional(row["page_ref"]),
                clause_ref=_optional(row["clause_ref"]),
                review_state=ReviewState.UNREVIEWED,
            )
        )
        if fact.fact_id in seen_ids:
            raise ValueError(f"CSV duplicate fact_id: {fact.fact_id}")
        seen_ids.add(fact.fact_id)
        facts.append(fact)

    if not facts:
        raise ValueError("CSV must contain at least one fact row")
    return CsvEvidencePreview(
        sha256=hashlib.sha256(content).hexdigest(),
        row_count=len(facts),
        facts=tuple(facts),
    )


def _source_row_matches(row: sqlite3.Row, source: EvidenceSource) -> bool:
    return (
        row["tenant_id"] == source.tenant_id
        and row["evidence_id"] == source.evidence_id
        and row["kind"] == source.kind.value
        and row["display_name"] == source.display_name
        and row["external_ref"] == source.external_ref
        and row["sha256"] == source.sha256
        and row["captured_at"] == source.captured_at
    )


def _fact_row_matches(row: sqlite3.Row, fact: ExtractedFact) -> bool:
    return (
        row["tenant_id"] == fact.tenant_id
        and row["fact_id"] == fact.fact_id
        and row["evidence_id"] == fact.evidence_id
        and row["fact_type"] == fact.fact_type.value
        and row["raw_value"] == fact.raw_value
        and row["normalized_value"] == fact.normalized_value
        and row["scope_ref"] == fact.scope_ref
        and row["page_ref"] == fact.page_ref
        and row["clause_ref"] == fact.clause_ref
        and row["review_state"] == ReviewState.UNREVIEWED.value
        and row["reviewed_at"] is None
    )


def commit_csv_import(
    *,
    db_path: str,
    source: EvidenceSource,
    preview: CsvEvidencePreview,
) -> tuple[bool, int]:
    """Atomically persist a CSV evidence source and its UNREVIEWED facts."""

    source = validate_source(source)
    if source.sha256 != preview.sha256:
        raise ValueError("evidence source sha256 does not match CSV preview")
    if any(fact.tenant_id != source.tenant_id or fact.evidence_id != source.evidence_id for fact in preview.facts):
        raise ValueError("CSV facts do not match evidence source identity")
    facts = tuple(validate_fact(item) for item in preview.facts)
    if any(item.review_state is not ReviewState.UNREVIEWED for item in facts):
        raise ValueError("CSV facts must remain UNREVIEWED")
    if len(facts) != preview.row_count:
        raise ValueError("CSV preview row count mismatch")

    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing_source = conn.execute(
            """
            SELECT tenant_id,evidence_id,kind,display_name,external_ref,sha256,captured_at
            FROM capacity_commitment_evidence_sources
            WHERE tenant_id=? AND evidence_id=?
            """,
            (source.tenant_id, source.evidence_id),
        ).fetchone()
        source_created = False
        if existing_source is None:
            conn.execute(
                """
                INSERT INTO capacity_commitment_evidence_sources
                (tenant_id,evidence_id,kind,display_name,external_ref,sha256,captured_at,created_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    source.tenant_id,
                    source.evidence_id,
                    source.kind.value,
                    source.display_name,
                    source.external_ref,
                    source.sha256,
                    source.captured_at,
                    now,
                ),
            )
            source_created = True
        elif not _source_row_matches(existing_source, source):
            raise FileExistsError("CSV evidence source already exists with different provenance")

        inserted = 0
        for fact in facts:
            existing = conn.execute(
                """
                SELECT tenant_id,fact_id,evidence_id,fact_type,raw_value,normalized_value,
                       scope_ref,page_ref,clause_ref,review_state,reviewed_at
                FROM capacity_commitment_evidence_facts
                WHERE tenant_id=? AND fact_id=?
                """,
                (fact.tenant_id, fact.fact_id),
            ).fetchone()
            if existing is not None:
                if not _fact_row_matches(existing, fact):
                    raise FileExistsError(f"CSV fact conflict: {fact.fact_id}")
                continue
            conn.execute(
                """
                INSERT INTO capacity_commitment_evidence_facts
                (tenant_id,fact_id,evidence_id,fact_type,raw_value,normalized_value,
                 scope_ref,page_ref,clause_ref,review_state,created_at,reviewed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL)
                """,
                (
                    fact.tenant_id,
                    fact.fact_id,
                    fact.evidence_id,
                    fact.fact_type.value,
                    fact.raw_value,
                    fact.normalized_value,
                    fact.scope_ref,
                    fact.page_ref,
                    fact.clause_ref,
                    fact.review_state.value,
                    now,
                ),
            )
            inserted += 1
        conn.commit()
        return source_created, inserted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
