from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class DocumentStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredDocument:
    tenant_id: str
    document_id: str
    source_ref: str
    original_name: str
    content_hash: str
    size_bytes: int
    stored_at: str


class DocumentStore:
    """Consumer-owned document bytes with immutable tenant-scoped metadata.

    Objects are addressed by SHA-256; logical document ids are tenant-scoped.
    The component grants no cross-app storage authority and performs no parsing.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.root.mkdir(parents=True, exist_ok=True)
        self.objects.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "documents.sqlite3"
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS documents(
                    tenant_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    stored_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id, document_id)
                )"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(tenant_id,content_hash)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.index_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _validate_identity(value: str, name: str) -> str:
        cleaned = str(value).strip()
        if not cleaned:
            raise DocumentStoreError(f"{name} is required")
        if "\x00" in cleaned:
            raise DocumentStoreError(f"invalid {name}")
        return cleaned

    def _object_path(self, content_hash: str) -> Path:
        if len(content_hash) != 64 or any(ch not in "0123456789abcdef" for ch in content_hash):
            raise DocumentStoreError("invalid content hash")
        return self.objects / content_hash[:2] / content_hash[2:]

    def put(
        self,
        *,
        tenant_id: str,
        document_id: str,
        source_ref: str,
        original_name: str,
        content: bytes,
    ) -> StoredDocument:
        tenant = self._validate_identity(tenant_id, "tenant_id")
        document = self._validate_identity(document_id, "document_id")
        source = self._validate_identity(source_ref, "source_ref")
        name = self._validate_identity(original_name, "original_name")
        payload = bytes(content)
        if not payload:
            raise DocumentStoreError("empty documents are rejected")
        content_hash = hashlib.sha256(payload).hexdigest()
        size = len(payload)
        stored_at = datetime.now(timezone.utc).isoformat()

        object_path = self._object_path(content_hash)
        object_path.parent.mkdir(parents=True, exist_ok=True)
        if object_path.exists():
            if hashlib.sha256(object_path.read_bytes()).hexdigest() != content_hash:
                raise DocumentStoreError("stored object hash mismatch")
        else:
            fd, temp_name = tempfile.mkstemp(prefix=".upload-", dir=object_path.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, object_path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM documents WHERE tenant_id=? AND document_id=?",
                (tenant, document),
            ).fetchone()
            if existing is not None:
                comparable = (existing["source_ref"], existing["original_name"], existing["content_hash"], existing["size_bytes"])
                expected = (source, name, content_hash, size)
                if comparable != expected:
                    raise DocumentStoreError("immutable tenant document id collision")
                return StoredDocument(
                    tenant, document, existing["source_ref"], existing["original_name"],
                    existing["content_hash"], int(existing["size_bytes"]), existing["stored_at"],
                )
            conn.execute(
                "INSERT INTO documents VALUES(?,?,?,?,?,?,?)",
                (tenant, document, source, name, content_hash, size, stored_at),
            )
        return StoredDocument(tenant, document, source, name, content_hash, size, stored_at)

    def get(self, *, tenant_id: str, document_id: str) -> tuple[StoredDocument, bytes]:
        tenant = self._validate_identity(tenant_id, "tenant_id")
        document = self._validate_identity(document_id, "document_id")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE tenant_id=? AND document_id=?",
                (tenant, document),
            ).fetchone()
        if row is None:
            raise DocumentStoreError("tenant-scoped document not found")
        record = StoredDocument(**dict(row))
        object_path = self._object_path(record.content_hash)
        if not object_path.is_file():
            raise DocumentStoreError("document object missing")
        payload = object_path.read_bytes()
        if len(payload) != record.size_bytes or hashlib.sha256(payload).hexdigest() != record.content_hash:
            raise DocumentStoreError("document object integrity failure")
        return record, payload

    def list(self, *, tenant_id: str) -> tuple[StoredDocument, ...]:
        tenant = self._validate_identity(tenant_id, "tenant_id")
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE tenant_id=? ORDER BY stored_at,document_id",
                (tenant,),
            ).fetchall()
        return tuple(StoredDocument(**dict(row)) for row in rows)
