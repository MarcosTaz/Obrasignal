from __future__ import annotations

import base64
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


_MAGIC = b"CCEV1\x00"
_NONCE_BYTES = 12
_MAX_EVIDENCE_BYTES = 25_000_000
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")


@dataclass(frozen=True)
class StoredEvidence:
    tenant_id: str
    evidence_id: str
    sha256: str
    byte_count: int
    storage_ref: str


def _safe_id(value, field):
    if not isinstance(value, str) or not _SAFE_ID_RE.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def decode_evidence_key(encoded: str) -> bytes:
    if not isinstance(encoded, str) or not encoded.strip():
        raise ValueError("evidence encryption key is required")
    try:
        key = base64.urlsafe_b64decode(encoded.strip() + "=" * (-len(encoded.strip()) % 4))
    except Exception as exc:
        raise ValueError("evidence encryption key must be URL-safe base64") from exc
    if len(key) != 32:
        raise ValueError("evidence encryption key must decode to exactly 32 bytes")
    return key


def generate_evidence_key() -> str:
    """Generate a deployable key value; never persists or logs it."""

    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")


class EvidenceVault:
    """Encrypted immutable evidence store for bounded pilot/customer files."""

    def __init__(self, root_path: str, key: bytes):
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("EvidenceVault key must be exactly 32 bytes")
        if not root_path:
            raise ValueError("evidence vault root_path is required")
        self.root = Path(root_path).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass
        self._aes = AESGCM(key)

    @classmethod
    def from_environment(cls):
        root = (os.getenv("CAPACITY_COMMITMENT_EVIDENCE_DIR") or "").strip()
        encoded = (os.getenv("CAPACITY_COMMITMENT_EVIDENCE_KEY") or "").strip()
        if not root or not encoded:
            raise RuntimeError(
                "CAPACITY_COMMITMENT_EVIDENCE_DIR and CAPACITY_COMMITMENT_EVIDENCE_KEY are required"
            )
        return cls(root, decode_evidence_key(encoded))

    @staticmethod
    def _object_name(tenant_id: str, evidence_id: str) -> str:
        identity = f"{tenant_id}\x00{evidence_id}".encode("utf-8")
        return hashlib.sha256(identity).hexdigest() + ".ccev"

    def _path(self, tenant_id: str, evidence_id: str) -> Path:
        tenant_id = _safe_id(tenant_id, "tenant_id")
        evidence_id = _safe_id(evidence_id, "evidence_id")
        tenant_dir = self.root / hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
        tenant_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(tenant_dir, 0o700)
        except OSError:
            pass
        return tenant_dir / self._object_name(tenant_id, evidence_id)

    @staticmethod
    def _aad(tenant_id: str, evidence_id: str, sha256: str) -> bytes:
        return f"CCEV1|{tenant_id}|{evidence_id}|{sha256}".encode("utf-8")

    def store(self, *, tenant_id: str, evidence_id: str, content: bytes) -> StoredEvidence:
        tenant_id = _safe_id(tenant_id, "tenant_id")
        evidence_id = _safe_id(evidence_id, "evidence_id")
        if not isinstance(content, bytes):
            raise ValueError("evidence content must be bytes")
        if not content:
            raise ValueError("evidence content is empty")
        if len(content) > _MAX_EVIDENCE_BYTES:
            raise ValueError("evidence content exceeds maximum size")
        sha256 = hashlib.sha256(content).hexdigest()
        path = self._path(tenant_id, evidence_id)
        aad = self._aad(tenant_id, evidence_id, sha256)

        if path.exists():
            existing = self.read(
                tenant_id=tenant_id,
                evidence_id=evidence_id,
                expected_sha256=sha256,
            )
            if existing != content:
                raise FileExistsError("evidence object exists with different plaintext")
            return StoredEvidence(tenant_id, evidence_id, sha256, len(content), f"vault:{evidence_id}")

        nonce = os.urandom(_NONCE_BYTES)
        ciphertext = self._aes.encrypt(nonce, content, aad)
        payload = _MAGIC + bytes.fromhex(sha256) + nonce + ciphertext
        fd, temporary = tempfile.mkstemp(prefix=".capacity-evidence-", dir=str(path.parent))
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        return StoredEvidence(tenant_id, evidence_id, sha256, len(content), f"vault:{evidence_id}")

    def read(self, *, tenant_id: str, evidence_id: str, expected_sha256: str) -> bytes:
        tenant_id = _safe_id(tenant_id, "tenant_id")
        evidence_id = _safe_id(evidence_id, "evidence_id")
        if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise ValueError("expected_sha256 must be lowercase SHA-256 hex")
        path = self._path(tenant_id, evidence_id)
        if not path.is_file():
            raise KeyError("evidence object not found")
        payload = path.read_bytes()
        minimum = len(_MAGIC) + 32 + _NONCE_BYTES + 16
        if len(payload) < minimum or not payload.startswith(_MAGIC):
            raise RuntimeError("evidence object envelope is invalid")
        offset = len(_MAGIC)
        stored_sha = payload[offset : offset + 32].hex()
        offset += 32
        if stored_sha != expected_sha256:
            raise RuntimeError("evidence object hash identity mismatch")
        nonce = payload[offset : offset + _NONCE_BYTES]
        ciphertext = payload[offset + _NONCE_BYTES :]
        try:
            content = self._aes.decrypt(
                nonce,
                ciphertext,
                self._aad(tenant_id, evidence_id, expected_sha256),
            )
        except Exception as exc:
            raise RuntimeError("evidence object authentication failed") from exc
        if hashlib.sha256(content).hexdigest() != expected_sha256:
            raise RuntimeError("evidence object plaintext hash mismatch")
        return content

    def exists(self, *, tenant_id: str, evidence_id: str) -> bool:
        return self._path(tenant_id, evidence_id).is_file()
