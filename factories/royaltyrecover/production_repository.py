from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from secure_repository import BACKUP_MAGIC, SecureRoyaltyRepository


class ProductionRoyaltyRepository(SecureRoyaltyRepository):
    """Final production repository boundary.

    Restore deliberately emits no synthetic organization event. The restored
    audit chain is verified exactly as it existed in the backup; operational
    restore logging belongs outside the tenant ledger (deployment/runbook log).
    """

    def restore_encrypted_from(self, source_path: str | Path, *, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES256_KEY_REQUIRED")
        blob = Path(source_path).read_bytes()
        offset = len(BACKUP_MAGIC)
        if len(blob) <= offset + 12 or not blob.startswith(BACKUP_MAGIC):
            raise ValueError("INVALID_ENCRYPTED_BACKUP")
        nonce = blob[offset:offset + 12]
        try:
            plain = AESGCM(key).decrypt(nonce, blob[offset + 12 :], BACKUP_MAGIC)
        except Exception as exc:
            raise ValueError("BACKUP_DECRYPTION_FAILED") from exc
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            source = Path(tmp.name)
            tmp.write(plain)
        try:
            with closing(sqlite3.connect(str(source))) as restored:
                check = restored.execute("PRAGMA integrity_check").fetchone()
                if not check or check[0] != "ok":
                    raise ValueError("BACKUP_INTEGRITY_FAILED")
                restored.backup(self.conn)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            if not self.integrity_check() or not self.verify_audit_chain():
                raise ValueError("RESTORE_VERIFICATION_FAILED")
        finally:
            source.unlink(missing_ok=True)
