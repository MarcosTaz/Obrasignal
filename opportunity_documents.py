"""Canonical opportunity document inventory contracts for ObraSignal.

This capability inventories public procurement document references. It does not
store document bytes, download files, parse PDFs, infer legal reuse rights, or
generate bid content. Opportunity/source records remain authoritative elsewhere.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Iterable, Literal, Mapping
from urllib.parse import urlsplit

DocumentType = Literal[
    "NOTICE", "SPECIFICATION", "TECHNICAL_SPECIFICATION", "BOQ", "DRAWING",
    "PRICING_SCHEDULE", "QUALIFICATION_FORM", "DECLARATION", "CONTRACT_DRAFT",
    "CLARIFICATION", "AMENDMENT", "CORRIGENDUM", "APPENDIX",
    "SUBMISSION_TEMPLATE", "OTHER", "UNKNOWN",
]
DocumentPurpose = Literal[
    "FOR_INFORMATION", "FOR_ANALYSIS", "FOR_QUALIFICATION", "FOR_PRICING",
    "FOR_SUBMISSION", "FOR_CONTRACT", "UNKNOWN",
]
DocumentStatus = Literal["CURRENT", "SUPERSEDED", "WITHDRAWN", "UNKNOWN"]
AvailabilityStatus = Literal[
    "AVAILABLE", "REFERENCE_ONLY", "UNAVAILABLE", "ACCESS_RESTRICTED", "MISSING", "UNKNOWN",
]
RequiredState = Literal["REQUIRED", "NOT_REQUIRED", "UNKNOWN"]
ClassificationBasis = Literal["SOURCE", "INFERRED", "UNKNOWN"]
RelationshipType = Literal["SUPERSEDES", "AMENDS", "APPENDS_TO", "RELATED_TO"]

_DOCUMENT_TYPES = {
    "NOTICE", "SPECIFICATION", "TECHNICAL_SPECIFICATION", "BOQ", "DRAWING",
    "PRICING_SCHEDULE", "QUALIFICATION_FORM", "DECLARATION", "CONTRACT_DRAFT",
    "CLARIFICATION", "AMENDMENT", "CORRIGENDUM", "APPENDIX",
    "SUBMISSION_TEMPLATE", "OTHER", "UNKNOWN",
}
_PURPOSES = {
    "FOR_INFORMATION", "FOR_ANALYSIS", "FOR_QUALIFICATION", "FOR_PRICING",
    "FOR_SUBMISSION", "FOR_CONTRACT", "UNKNOWN",
}
_STATUSES = {"CURRENT", "SUPERSEDED", "WITHDRAWN", "UNKNOWN"}
_AVAILABILITY = {"AVAILABLE", "REFERENCE_ONLY", "UNAVAILABLE", "ACCESS_RESTRICTED", "MISSING", "UNKNOWN"}
_REQUIRED = {"REQUIRED", "NOT_REQUIRED", "UNKNOWN"}
_RELATIONSHIPS = {"SUPERSEDES", "AMENDS", "APPENDS_TO", "RELATED_TO"}
_MAX_TEXT = 4096
_MAX_METADATA_BYTES = 65536

_FALSE_POSITIVE_MARKERS = (
    "guidance", "example", "examples", "sample", "how to", "manual", "instructions",
)
_TYPE_RULES: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    ("CORRIGENDUM", (re.compile(r"\bcorrigendum\b", re.I), re.compile(r"\berrat(?:um|a)\b", re.I))),
    ("CLARIFICATION", (re.compile(r"\bclarification(?:s)?\b", re.I), re.compile(r"\bquestions?\s*(?:and|&)\s*answers?\b", re.I))),
    ("AMENDMENT", (re.compile(r"\bamendment\b", re.I), re.compile(r"\baddendum\b", re.I))),
    ("TECHNICAL_SPECIFICATION", (re.compile(r"\btechnical\s+specification(?:s)?\b", re.I), re.compile(r"\btech(?:nical)?[-_ ]?spec(?:ification)?s?\b", re.I))),
    ("BOQ", (re.compile(r"\bbill\s+of\s+quantit(?:y|ies)\b", re.I), re.compile(r"(?:^|[^a-z0-9])boq(?:[^a-z0-9]|$)", re.I))),
    ("PRICING_SCHEDULE", (re.compile(r"\bprice|pricing\s+schedule\b", re.I), re.compile(r"\bschedule\s+of\s+rates\b", re.I))),
    ("CONTRACT_DRAFT", (re.compile(r"\bdraft\s+contract\b", re.I), re.compile(r"\bcontract\s+draft\b", re.I))),
    ("QUALIFICATION_FORM", (re.compile(r"\bqualification\s+form\b", re.I), re.compile(r"\bpre[- ]?qualification\b", re.I))),
    ("SUBMISSION_TEMPLATE", (re.compile(r"\bsubmission\s+(?:form|template)\b", re.I), re.compile(r"\btender\s+form\b", re.I))),
    ("DECLARATION", (re.compile(r"\bdeclaration\b", re.I),)),
    ("DRAWING", (re.compile(r"\bdrawing(?:s)?\b", re.I), re.compile(r"\bplan(?:s)?\b", re.I))),
    ("APPENDIX", (re.compile(r"\bappendix\b", re.I), re.compile(r"\bannex\b", re.I))),
    ("SPECIFICATION", (re.compile(r"\bspecification(?:s)?\b", re.I),)),
    ("NOTICE", (re.compile(r"\bprocurement\s+notice\b", re.I), re.compile(r"\btender\s+notice\b", re.I))),
)


def _text(value, *, limit=_MAX_TEXT) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\x00", "")
    return text[:limit]


def _enum(value, allowed, default):
    candidate = _text(value, limit=80).upper()
    return candidate if candidate in allowed else default


def safe_external_url(value: object) -> str | None:
    """Return only absolute HTTP(S) URLs; never convert unsafe schemes."""
    text = _text(value)
    if not text:
        return None
    try:
        parsed = urlsplit(text)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    return text


def classify_document_type(title: object, explicit_type: object = None) -> tuple[DocumentType, ClassificationBasis]:
    """Classify conservatively; source metadata wins and heuristic guidance stays UNKNOWN."""
    explicit = _enum(explicit_type, _DOCUMENT_TYPES, "")
    if explicit:
        return explicit, "SOURCE"
    text = _text(title).lower()
    if not text:
        return "UNKNOWN", "UNKNOWN"
    if any(marker in text for marker in _FALSE_POSITIVE_MARKERS):
        return "UNKNOWN", "UNKNOWN"
    for document_type, patterns in _TYPE_RULES:
        if any(pattern.search(text) for pattern in patterns):
            return document_type, "INFERRED"
    return "UNKNOWN", "UNKNOWN"


def metadata_fingerprint(reference: Mapping[str, object]) -> str:
    """Metadata fingerprint; explicitly not a content hash."""
    material = {
        "source": _text(reference.get("source"), limit=200).lower(),
        "opportunity_source": _text(reference.get("opportunity_source"), limit=200).lower(),
        "opportunity_external_id": _text(reference.get("opportunity_external_id"), limit=500),
        "external_id": _text(reference.get("external_id"), limit=1000),
        "title": _text(reference.get("title")).casefold(),
        "version": _text(reference.get("version"), limit=200).casefold(),
        "published_at": _text(reference.get("published_at"), limit=100),
        "mime_type": _text(reference.get("mime_type"), limit=200).lower(),
    }
    payload = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def content_fingerprint(data: bytes) -> str:
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("content fingerprint requires bytes")
    return sha256(bytes(data)).hexdigest()


@dataclass(frozen=True)
class DocumentRelationship:
    relationship_type: RelationshipType
    target_document_id: str


@dataclass(frozen=True)
class OpportunityDocument:
    document_id: str
    opportunity_source: str
    opportunity_external_id: str
    source: str
    external_id: str | None
    title: str
    document_type: DocumentType
    classification_basis: ClassificationBasis
    purpose: DocumentPurpose
    required_for_submission: RequiredState
    status: DocumentStatus
    availability_status: AvailabilityStatus
    source_reference: str | None = None
    source_url: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    updated_at: str | None = None
    effective_at: str | None = None
    mime_type: str | None = None
    language: str | None = None
    version: str | None = None
    content_fingerprint: str | None = None
    fingerprint_kind: Literal["CONTENT", "METADATA"] = "METADATA"
    file_size: int | None = None
    package_reference: str | None = None
    parsed: bool | None = None
    relationships: tuple[DocumentRelationship, ...] = ()
    raw_metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        value = asdict(self)
        value["relationships"] = [asdict(item) for item in self.relationships]
        return value


@dataclass(frozen=True)
class OpportunityDocumentInventory:
    current_documents: tuple[OpportunityDocument, ...]
    superseded_documents: tuple[OpportunityDocument, ...]
    missing_or_unavailable: tuple[OpportunityDocument, ...]
    unknown_documents: tuple[OpportunityDocument, ...]
    submission_related: tuple[OpportunityDocument, ...]
    analysis_related: tuple[OpportunityDocument, ...]
    needs_verification: tuple[OpportunityDocument, ...]
    generated_at: str
    inventory_version: str = "document_inventory.v0"

    def to_dict(self) -> dict:
        return {
            "current_documents": [item.to_dict() for item in self.current_documents],
            "superseded_documents": [item.to_dict() for item in self.superseded_documents],
            "missing_or_unavailable": [item.to_dict() for item in self.missing_or_unavailable],
            "unknown_documents": [item.to_dict() for item in self.unknown_documents],
            "submission_related": [item.to_dict() for item in self.submission_related],
            "analysis_related": [item.to_dict() for item in self.analysis_related],
            "needs_verification": [item.to_dict() for item in self.needs_verification],
            "generated_at": self.generated_at,
            "inventory_version": self.inventory_version,
        }


def _raw_metadata(value: object) -> dict:
    if not isinstance(value, Mapping):
        return {}
    cleaned = {str(k)[:200]: v for k, v in value.items()}
    encoded = json.dumps(cleaned, ensure_ascii=False, sort_keys=True, default=str)
    if len(encoded.encode("utf-8")) > _MAX_METADATA_BYTES:
        raise ValueError("document metadata exceeds 65536 bytes")
    return json.loads(encoded)


def _identity_basis(reference: Mapping[str, object], metadata_hash: str) -> tuple[str, str]:
    source = _text(reference.get("source"), limit=200).lower()
    native = _text(reference.get("external_id"), limit=1000)
    version = _text(reference.get("version"), limit=200)
    explicit_content_hash = _text(reference.get("content_fingerprint"), limit=128).lower()
    fingerprint_kind = _enum(reference.get("fingerprint_kind"), {"CONTENT", "METADATA"}, "")
    if explicit_content_hash and fingerprint_kind == "CONTENT":
        # Content identity distinguishes same-filename/native-id changed bytes.
        native_prefix = f"native:{source}:{native}:" if native else ""
        return f"{native_prefix}content:{explicit_content_hash}", "CONTENT"
    if native:
        return f"native:{source}:{native}:version:{version or 'unknown'}", "METADATA"
    return f"metadata:{metadata_hash}", "METADATA"


def normalize_document_reference(reference: Mapping[str, object]) -> OpportunityDocument:
    if not isinstance(reference, Mapping):
        raise TypeError("document reference must be a mapping")
    opportunity_source = _text(reference.get("opportunity_source"), limit=200)
    opportunity_external_id = _text(reference.get("opportunity_external_id"), limit=1000)
    source = _text(reference.get("source"), limit=200) or opportunity_source
    if not opportunity_source or not opportunity_external_id or not source:
        raise ValueError("opportunity_source, opportunity_external_id and source are required")

    title = _text(reference.get("title"))
    document_type, classification_basis = classify_document_type(title, reference.get("document_type"))
    metadata_hash = metadata_fingerprint(reference)
    identity_basis, fingerprint_kind = _identity_basis(reference, metadata_hash)
    document_id = "doc_" + sha256(
        f"{opportunity_source.casefold()}\x1f{opportunity_external_id}\x1f{identity_basis}".encode("utf-8")
    ).hexdigest()[:24]

    raw_url = _text(reference.get("source_url") or reference.get("url"))
    source_url = safe_external_url(raw_url)
    availability = _enum(reference.get("availability_status"), _AVAILABILITY, "UNKNOWN")
    if raw_url and source_url is None and availability == "AVAILABLE":
        availability = "REFERENCE_ONLY"

    status = _enum(reference.get("status"), _STATUSES, "UNKNOWN")
    purpose = _enum(reference.get("purpose"), _PURPOSES, "UNKNOWN")
    required = _enum(reference.get("required_for_submission"), _REQUIRED, "UNKNOWN")
    file_size = reference.get("file_size")
    if file_size is not None:
        if isinstance(file_size, bool) or not isinstance(file_size, int) or file_size < 0:
            raise ValueError("file_size must be a non-negative integer when known")

    raw = _raw_metadata(reference.get("metadata") or {})
    if raw_url and source_url is None:
        raw.setdefault("unsafe_source_url_rejected", True)

    return OpportunityDocument(
        document_id=document_id,
        opportunity_source=opportunity_source,
        opportunity_external_id=opportunity_external_id,
        source=source,
        external_id=_text(reference.get("external_id"), limit=1000) or None,
        title=title,
        document_type=document_type,
        classification_basis=classification_basis,
        purpose=purpose,
        required_for_submission=required,
        status=status,
        availability_status=availability,
        source_reference=_text(reference.get("source_reference"), limit=2000) or None,
        source_url=source_url,
        publisher=_text(reference.get("publisher"), limit=1000) or None,
        published_at=_text(reference.get("published_at"), limit=100) or None,
        updated_at=_text(reference.get("updated_at"), limit=100) or None,
        effective_at=_text(reference.get("effective_at"), limit=100) or None,
        mime_type=_text(reference.get("mime_type"), limit=200) or None,
        language=_text(reference.get("language"), limit=100) or None,
        version=_text(reference.get("version"), limit=200) or None,
        content_fingerprint=_text(reference.get("content_fingerprint"), limit=128).lower() or metadata_hash,
        fingerprint_kind=fingerprint_kind,
        file_size=file_size,
        package_reference=_text(reference.get("package_reference"), limit=1000) or None,
        parsed=reference.get("parsed") if isinstance(reference.get("parsed"), bool) else None,
        raw_metadata=raw,
    )


def _with_relationships(document: OpportunityDocument, relationships: Iterable[DocumentRelationship], *, status=None):
    data = document.to_dict()
    data["relationships"] = tuple(relationships)
    if status is not None:
        data["status"] = status
    return OpportunityDocument(**data)


def normalize_document_references(references: Iterable[Mapping[str, object]]) -> tuple[OpportunityDocument, ...]:
    """Normalize, dedupe and apply only explicit supersession relations.

    Input ordering has no effect on identity or output ordering.
    """
    normalized: dict[str, OpportunityDocument] = {}
    raw_by_id: dict[str, Mapping[str, object]] = {}
    for reference in references or ():
        document = normalize_document_reference(reference)
        if document.document_id not in normalized:
            normalized[document.document_id] = document
            raw_by_id[document.document_id] = reference

    # Resolve explicit supersedes_document_id or source-native target IDs. Never
    # guess that a later timestamp/version supersedes an earlier document.
    native_index: dict[tuple[str, str], list[str]] = {}
    for document in normalized.values():
        if document.external_id:
            native_index.setdefault((document.source.casefold(), document.external_id), []).append(document.document_id)

    superseded_targets: set[str] = set()
    result: dict[str, OpportunityDocument] = dict(normalized)
    for document_id, document in normalized.items():
        raw = raw_by_id[document_id]
        relationships: list[DocumentRelationship] = []
        explicit_target = _text(raw.get("supersedes_document_id"), limit=200)
        native_target = _text(raw.get("supersedes_external_id"), limit=1000)
        target_id = explicit_target if explicit_target in normalized else ""
        if not target_id and native_target:
            candidates = [candidate for candidate in native_index.get((document.source.casefold(), native_target), []) if candidate != document_id]
            if len(candidates) == 1:
                target_id = candidates[0]
        if target_id:
            relationships.append(DocumentRelationship("SUPERSEDES", target_id))
            superseded_targets.add(target_id)
        relation_type = _enum(raw.get("relationship_type"), _RELATIONSHIPS, "")
        relation_target = _text(raw.get("related_document_id"), limit=200)
        if relation_type and relation_target in normalized and relation_target != document_id:
            relationships.append(DocumentRelationship(relation_type, relation_target))
        if relationships:
            result[document_id] = _with_relationships(document, relationships)

    for target_id in superseded_targets:
        target = result[target_id]
        if target.status != "WITHDRAWN":
            result[target_id] = _with_relationships(target, target.relationships, status="SUPERSEDED")

    return tuple(sorted(result.values(), key=lambda item: (item.title.casefold(), item.document_id)))


def build_document_inventory(references: Iterable[Mapping[str, object]], *, generated_at: str | None = None) -> OpportunityDocumentInventory:
    documents = normalize_document_references(references)
    current = tuple(item for item in documents if item.status == "CURRENT")
    superseded = tuple(item for item in documents if item.status in {"SUPERSEDED", "WITHDRAWN"})
    unavailable = tuple(item for item in documents if item.availability_status in {"UNAVAILABLE", "ACCESS_RESTRICTED", "MISSING"})
    unknown = tuple(item for item in documents if item.document_type == "UNKNOWN")
    submission = tuple(item for item in documents if item.purpose == "FOR_SUBMISSION" or item.required_for_submission == "REQUIRED")
    analysis = tuple(item for item in documents if item.purpose == "FOR_ANALYSIS")
    needs_verification = tuple(
        item for item in documents
        if item.status == "UNKNOWN" or item.availability_status == "UNKNOWN" or item.required_for_submission == "UNKNOWN"
    )
    return OpportunityDocumentInventory(
        current_documents=current,
        superseded_documents=superseded,
        missing_or_unavailable=unavailable,
        unknown_documents=unknown,
        submission_related=submission,
        analysis_related=analysis,
        needs_verification=needs_verification,
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
    )


def ensure_document_tables(conn) -> None:
    conn.execute('''CREATE TABLE IF NOT EXISTS opportunity_documents (
        document_id TEXT PRIMARY KEY,
        opportunity_source TEXT NOT NULL,
        opportunity_external_id TEXT NOT NULL,
        source TEXT NOT NULL,
        external_id TEXT,
        title TEXT NOT NULL,
        document_type TEXT NOT NULL,
        classification_basis TEXT NOT NULL,
        purpose TEXT NOT NULL,
        required_for_submission TEXT NOT NULL,
        status TEXT NOT NULL,
        availability_status TEXT NOT NULL,
        source_reference TEXT,
        source_url TEXT,
        publisher TEXT,
        published_at TEXT,
        updated_at TEXT,
        effective_at TEXT,
        mime_type TEXT,
        language TEXT,
        version TEXT,
        content_fingerprint TEXT NOT NULL,
        fingerprint_kind TEXT NOT NULL,
        file_size INTEGER,
        package_reference TEXT,
        parsed INTEGER,
        raw_metadata_json TEXT NOT NULL DEFAULT '{}',
        first_observed TEXT NOT NULL,
        last_observed TEXT NOT NULL
    )''')
    conn.execute('''CREATE INDEX IF NOT EXISTS idx_opportunity_documents_opportunity
        ON opportunity_documents(opportunity_source, opportunity_external_id)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS opportunity_document_relationships (
        source_document_id TEXT NOT NULL,
        relationship_type TEXT NOT NULL,
        target_document_id TEXT NOT NULL,
        PRIMARY KEY(source_document_id, relationship_type, target_document_id),
        FOREIGN KEY(source_document_id) REFERENCES opportunity_documents(document_id),
        FOREIGN KEY(target_document_id) REFERENCES opportunity_documents(document_id)
    )''')


def ingest_document_references(conn, references: Iterable[Mapping[str, object]], *, observed_at: str | None = None, commit=True) -> int:
    """Idempotently persist normalized public document metadata only."""
    ensure_document_tables(conn)
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    documents = normalize_document_references(references)
    for document in documents:
        conn.execute('''INSERT INTO opportunity_documents(
            document_id, opportunity_source, opportunity_external_id, source, external_id, title,
            document_type, classification_basis, purpose, required_for_submission, status,
            availability_status, source_reference, source_url, publisher, published_at, updated_at,
            effective_at, mime_type, language, version, content_fingerprint, fingerprint_kind,
            file_size, package_reference, parsed, raw_metadata_json, first_observed, last_observed
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(document_id) DO UPDATE SET
            title=excluded.title, document_type=excluded.document_type,
            classification_basis=excluded.classification_basis, purpose=excluded.purpose,
            required_for_submission=excluded.required_for_submission, status=excluded.status,
            availability_status=excluded.availability_status, source_reference=excluded.source_reference,
            source_url=excluded.source_url, publisher=excluded.publisher, published_at=excluded.published_at,
            updated_at=excluded.updated_at, effective_at=excluded.effective_at, mime_type=excluded.mime_type,
            language=excluded.language, version=excluded.version, file_size=excluded.file_size,
            package_reference=excluded.package_reference, parsed=excluded.parsed,
            raw_metadata_json=excluded.raw_metadata_json, last_observed=excluded.last_observed''',
            (
                document.document_id, document.opportunity_source, document.opportunity_external_id,
                document.source, document.external_id, document.title, document.document_type,
                document.classification_basis, document.purpose, document.required_for_submission,
                document.status, document.availability_status, document.source_reference,
                document.source_url, document.publisher, document.published_at, document.updated_at,
                document.effective_at, document.mime_type, document.language, document.version,
                document.content_fingerprint, document.fingerprint_kind, document.file_size,
                document.package_reference, None if document.parsed is None else int(document.parsed),
                json.dumps(document.raw_metadata, ensure_ascii=False, sort_keys=True), observed, observed,
            ),
        )
        conn.execute("DELETE FROM opportunity_document_relationships WHERE source_document_id=?", (document.document_id,))
        for relationship in document.relationships:
            conn.execute('''INSERT OR IGNORE INTO opportunity_document_relationships(
                source_document_id, relationship_type, target_document_id) VALUES(?,?,?)''',
                (document.document_id, relationship.relationship_type, relationship.target_document_id))
    if commit:
        conn.commit()
    return len(documents)


def _row_to_document(row, relationships=()) -> OpportunityDocument:
    value = dict(row)
    value.pop("first_observed", None)
    value.pop("last_observed", None)
    raw = value.pop("raw_metadata_json", "{}")
    value["raw_metadata"] = json.loads(raw or "{}")
    parsed = value.get("parsed")
    value["parsed"] = None if parsed is None else bool(parsed)
    value["relationships"] = tuple(relationships)
    return OpportunityDocument(**value)


def get_document_inventory(conn, opportunity_source: str, opportunity_external_id: str) -> OpportunityDocumentInventory:
    """Read metadata only. No file fetch/materialization occurs here."""
    ensure_document_tables(conn)
    rows = conn.execute('''SELECT * FROM opportunity_documents
        WHERE opportunity_source=? AND opportunity_external_id=? ORDER BY title COLLATE NOCASE, document_id''',
        (opportunity_source, opportunity_external_id)).fetchall()
    ids = [row["document_id"] for row in rows]
    rels: dict[str, list[DocumentRelationship]] = {document_id: [] for document_id in ids}
    if ids:
        placeholders = ",".join("?" for _ in ids)
        for row in conn.execute(f'''SELECT source_document_id, relationship_type, target_document_id
            FROM opportunity_document_relationships WHERE source_document_id IN ({placeholders})''', ids).fetchall():
            rels[row["source_document_id"]].append(DocumentRelationship(row["relationship_type"], row["target_document_id"]))
    documents = tuple(_row_to_document(row, rels.get(row["document_id"], ())) for row in rows)
    return OpportunityDocumentInventory(
        current_documents=tuple(item for item in documents if item.status == "CURRENT"),
        superseded_documents=tuple(item for item in documents if item.status in {"SUPERSEDED", "WITHDRAWN"}),
        missing_or_unavailable=tuple(item for item in documents if item.availability_status in {"UNAVAILABLE", "ACCESS_RESTRICTED", "MISSING"}),
        unknown_documents=tuple(item for item in documents if item.document_type == "UNKNOWN"),
        submission_related=tuple(item for item in documents if item.purpose == "FOR_SUBMISSION" or item.required_for_submission == "REQUIRED"),
        analysis_related=tuple(item for item in documents if item.purpose == "FOR_ANALYSIS"),
        needs_verification=tuple(item for item in documents if item.status == "UNKNOWN" or item.availability_status == "UNKNOWN" or item.required_for_submission == "UNKNOWN"),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
