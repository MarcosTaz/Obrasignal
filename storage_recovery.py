"""Safe SQLite backup/restore helpers and disaster-recovery artifact contract.

Production paths are never selected implicitly. Backups/restores are create-only,
privacy-safe and structurally verified. Off-disk upload is intentionally outside
this module: providers must consume a verified artifact + manifest.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from storage_contract import contract_fingerprint


class StorageRecoveryError(RuntimeError):
    pass


ARTIFACT_FORMAT_VERSION = 1
DEFAULT_RPO_HOURS = 24
DEFAULT_RTO_HOURS = 4
DEFAULT_RETENTION_DAYS = 30


def _path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.name:
        raise StorageRecoveryError("database path must name a file")
    return path


def _open_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise StorageRecoveryError(f"source database does not exist: {path}")
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _integrity(conn: sqlite3.Connection) -> tuple[str, ...]:
    return tuple(str(row[0]) for row in conn.execute("PRAGMA integrity_check").fetchall())


def _schema_fingerprint(conn: sqlite3.Connection) -> str:
    rows = conn.execute("SELECT type,name,tbl_name,COALESCE(sql,'') FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name,tbl_name").fetchall()
    payload = "\n".join("|".join(str(v) for v in row) for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_database(path: str | Path) -> dict[str, Any]:
    source = _path(path)
    conn = _open_read_only(source)
    try:
        if _integrity(conn) != ("ok",):
            raise StorageRecoveryError("database integrity_check failed")
        return {
            "ok": True,
            "schema_fingerprint": _schema_fingerprint(conn),
            # Expected contract is repository evidence only. It is deliberately
            # not stored in the database and does not act as a migration ledger.
            "expected_contract_fingerprint": contract_fingerprint(include_runtime=True),
            "page_count": int(conn.execute("PRAGMA page_count").fetchone()[0]),
            "freelist_count": int(conn.execute("PRAGMA freelist_count").fetchone()[0]),
            "user_version": int(conn.execute("PRAGMA user_version").fetchone()[0]),
        }
    finally:
        conn.close()


def _copy_database(source: Path, destination: Path) -> dict[str, Any]:
    if source == destination:
        raise StorageRecoveryError("source and destination must differ")
    if destination.exists():
        raise StorageRecoveryError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = _open_read_only(source)
    dst = None
    try:
        before = _schema_fingerprint(src)
        dst = sqlite3.connect(str(destination), timeout=30)
        src.backup(dst)
        dst.commit()
        if _integrity(dst) != ("ok",):
            raise StorageRecoveryError("copied database integrity_check failed")
        after = _schema_fingerprint(dst)
        if before != after:
            raise StorageRecoveryError("copied database schema fingerprint mismatch")
        return {"ok": True, "source_schema_fingerprint": before, "destination_schema_fingerprint": after, "destination": str(destination)}
    except Exception:
        if dst is not None:
            dst.close(); dst = None
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        src.close()
        if dst is not None:
            dst.close()


def backup_database(source: str | Path, destination: str | Path) -> dict[str, Any]:
    return _copy_database(_path(source), _path(destination))


def restore_database(backup: str | Path, destination: str | Path) -> dict[str, Any]:
    return _copy_database(_path(backup), _path(destination))


def _safe_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "backup").strip()).strip("-.")
    return label or "backup"


def deterministic_artifact_name(*, label: str, created_at: datetime, schema_fingerprint: str) -> str:
    when = created_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"obrasignal-{_safe_label(label)}-{when}-{schema_fingerprint[:12]}.sqlite"


def create_backup_artifact(source: str | Path, directory: str | Path, *, label: str = "scheduled", created_at: datetime | None = None, source_revision: str | None = None) -> dict[str, Any]:
    source_path = _path(source)
    created = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    health = inspect_database(source_path)
    destination_dir = Path(directory).expanduser().resolve()
    name = deterministic_artifact_name(label=label, created_at=created, schema_fingerprint=health["schema_fingerprint"])
    artifact = destination_dir / name
    result = backup_database(source_path, artifact)
    manifest = artifact.with_suffix(artifact.suffix + ".manifest.json")
    if manifest.exists():
        artifact.unlink(missing_ok=True)
        raise StorageRecoveryError(f"manifest already exists: {manifest}")
    metadata = {
        "artifact_format_version": ARTIFACT_FORMAT_VERSION,
        "created_at": created.isoformat(),
        "artifact_name": artifact.name,
        "artifact_sha256": _sha256_file(artifact),
        "schema_fingerprint": result["destination_schema_fingerprint"],
        "expected_contract_fingerprint": health["expected_contract_fingerprint"],
        "source_revision": source_revision,
        "rpo_hours": DEFAULT_RPO_HOURS,
        "rto_hours": DEFAULT_RTO_HOURS,
        "retention_days": DEFAULT_RETENTION_DAYS,
        "off_disk_required": True,
        "encrypted_at_rest_required": True,
    }
    manifest.write_text(json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"ok": True, "artifact": str(artifact), "manifest": str(manifest), **metadata}


def verify_backup_artifact(artifact: str | Path, manifest: str | Path) -> dict[str, Any]:
    artifact_path = _path(artifact)
    manifest_path = _path(manifest)
    try:
        metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise StorageRecoveryError("backup manifest is unreadable") from exc
    required = {"artifact_format_version","artifact_name","artifact_sha256","schema_fingerprint","off_disk_required","encrypted_at_rest_required"}
    if not isinstance(metadata, dict) or not required <= set(metadata):
        raise StorageRecoveryError("backup manifest is incomplete")
    if metadata["artifact_format_version"] != ARTIFACT_FORMAT_VERSION:
        raise StorageRecoveryError("unsupported backup artifact format")
    if metadata["artifact_name"] != artifact_path.name:
        raise StorageRecoveryError("backup artifact name mismatch")
    if metadata["artifact_sha256"] != _sha256_file(artifact_path):
        raise StorageRecoveryError("backup artifact checksum mismatch")
    health = inspect_database(artifact_path)
    if metadata["schema_fingerprint"] != health["schema_fingerprint"]:
        raise StorageRecoveryError("backup artifact schema fingerprint mismatch")
    return {
        "ok": True,
        "schema_fingerprint": health["schema_fingerprint"],
        "expected_contract_fingerprint": metadata.get("expected_contract_fingerprint"),
        "artifact_sha256": metadata["artifact_sha256"],
    }


def verified_restore_drill(artifact: str | Path, manifest: str | Path, destination: str | Path) -> dict[str, Any]:
    verified = verify_backup_artifact(artifact, manifest)
    result = restore_database(artifact, destination)
    restored = inspect_database(destination)
    if restored["schema_fingerprint"] != verified["schema_fingerprint"]:
        Path(destination).unlink(missing_ok=True)
        raise StorageRecoveryError("restore drill schema mismatch")
    return {"ok": True, "destination": str(_path(destination)), "schema_fingerprint": restored["schema_fingerprint"]}


def production_cutover_guard(candidate: str | Path, *, expected_schema_fingerprint: str, explicit_operator_ack: bool = False) -> dict[str, Any]:
    """Validate a candidate only; never swaps/replaces the production DB."""
    if not explicit_operator_ack:
        raise StorageRecoveryError("production cutover requires explicit operator acknowledgement")
    health = inspect_database(candidate)
    if health["schema_fingerprint"] != expected_schema_fingerprint:
        raise StorageRecoveryError("production cutover candidate schema mismatch")
    return {"ok": True, "candidate_verified": True, "cutover_performed": False}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ObraSignal SQLite recovery utility")
    sub = p.add_subparsers(dest="command", required=True)
    v = sub.add_parser("verify"); v.add_argument("path")
    b = sub.add_parser("backup"); b.add_argument("source"); b.add_argument("destination")
    r = sub.add_parser("restore"); r.add_argument("backup"); r.add_argument("destination")
    a = sub.add_parser("artifact"); a.add_argument("source"); a.add_argument("directory"); a.add_argument("--label", default="scheduled"); a.add_argument("--source-revision")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "verify": result = inspect_database(args.path)
        elif args.command == "backup": result = backup_database(args.source, args.destination)
        elif args.command == "restore": result = restore_database(args.backup, args.destination)
        else: result = create_backup_artifact(args.source, args.directory, label=args.label, source_revision=args.source_revision)
    except StorageRecoveryError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True)); return 2
    print(json.dumps(result, sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
