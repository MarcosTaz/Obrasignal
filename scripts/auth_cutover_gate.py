#!/usr/bin/env python3
"""Offline, fail-closed ObraSignal identity mapping preflight.

Consumes private operator-created manifests; makes no HTTP/SQL calls, performs no
migration and never prints email, account ID, JWT or database credentials.
A PASS is an internal prerequisite, not permission to change production.
"""
import argparse
import json
import re
from pathlib import Path

_COMMIT = re.compile(r"^[a-fA-F0-9]{40}$")
_EVIDENCE = (
    "legacy_export_complete", "identity_migration_confirmed",
    "neon_positive_invited_login", "anonymous_sign_up_denied",
    "jwt_signature_issuer_audience", "tenant_isolation",
    "recovery_test", "backups_restorable", "rollback_rehearsed",
    "production_build_exact", "live_provider_verified",
)

class GateBlocked(ValueError):
    """One or more non-negotiable conditions of identity recovery is missing."""


def _field(record, key):
    value = record.get(key) if isinstance(record, dict) else None
    if not isinstance(value, str) or not (1 <= len(value.strip()) <= 200):
        raise GateBlocked("INVALID_IDENTITY_RECORD")
    if "@" in value or any(ord(ch) < 32 for ch in value):
        raise GateBlocked("INVALID_IDENTITY_RECORD")
    return value.strip()


def _accounts(data):
    raw = data.get("accounts") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raise GateBlocked("LEGACY_EXPORT_MISSING")
    pairs = set()
    for account in raw:
        pair = (_field(account,"legacy_subject"), _field(account,"company_id"))
        if pair in pairs:
            raise GateBlocked("LEGACY_PAIR_DUPLICATED")
        pairs.add(pair)
    if data.get("expected_pairs") != len(pairs):
        raise GateBlocked("LEGACY_EXPORT_INCOMPLETE")
    return pairs


def _mappings(data):
    raw = data.get("mappings") if isinstance(data, dict) else None
    if not isinstance(raw,list):
        raise GateBlocked("TARGET_MAPPING_MISSING")
    by_old = {}
    pairs = set()
    new_ownership = {}
    for row in raw:
        old = _field(row,"legacy_subject")
        new = _field(row,"neon_subject")
        company = _field(row,"company_id")
        pair = (old,company)
        if pair in pairs: raise GateBlocked("MAPPING_DUPLICATED")
        pairs.add(pair)
        if old in by_old and by_old[old] != new:
            raise GateBlocked("LEGACY_IDENTITY_SPLIT")
        by_old[old] = new
        if new in new_ownership and new_ownership[new] != old:
            raise GateBlocked("TARGET_IDENTITY_COLLISION")
        new_ownership[new] = old
    if data.get("expected_pairs") != len(pairs):
        raise GateBlocked("MAPPING_EXPORT_INCOMPLETE")
    return pairs, by_old


def evaluate(legacy, proposed, evidence, expected_commit):
    if not isinstance(expected_commit, str) or not _COMMIT.fullmatch(expected_commit):
        raise GateBlocked("EXPECTED_COMMIT_INVALID")
    if not isinstance(evidence, dict) or evidence.get("checked_commit") != expected_commit:
        raise GateBlocked("EXACT_COMMIT_NOT_PROVEN")
    missing = [k for k in _EVIDENCE if evidence.get(k) is not True]
    if missing:
        raise GateBlocked("RELEASE_EVIDENCE_MISSING:" + ",".join(missing))
    old = _accounts(legacy)
    mapped, identities = _mappings(proposed)
    if not old:
        raise GateBlocked("NO_EXISTING_IDENTITY_PRESERVATION_PROOF")
    if old != mapped:
        raise GateBlocked("IDENTITY_OR_TENANT_COVERAGE_MISMATCH")
    return {"legacy_membership_pairs":len(old),"distinct_identities":len(identities),
            "result":"MAPPING_GATE_PASS_NOT_RELEASE_AUTHORIZATION"}


def main(argv=None):
    parser=argparse.ArgumentParser(description="Fail-closed read-only identity cutover preflight")
    parser.add_argument("--legacy",required=True)
    parser.add_argument("--proposed",required=True)
    parser.add_argument("--evidence",required=True)
    parser.add_argument("--commit",required=True)
    args=parser.parse_args(argv)
    try:
        sources=[]
        for name in (args.legacy,args.proposed,args.evidence):
            with Path(name).open(encoding="utf-8") as stream:
                sources.append(json.load(stream))
        result=evaluate(*sources,expected_commit=args.commit)
    except (OSError, UnicodeError, json.JSONDecodeError,GateBlocked) as exc:
        # Reduce unexpected file/JSON errors to classes; never print contents.
        code = str(exc) if isinstance(exc,GateBlocked) else "MANIFEST_UNREADABLE"
        print("CUTOVER_BLOCKED:"+code)
        return 1
    print("CUTOVER_PREFLIGHT="+result["result"])
    print("MEMBERSHIP_PAIRS_VERIFIED="+str(result["legacy_membership_pairs"]))
    print("DISTINCT_IDENTITIES_VERIFIED="+str(result["distinct_identities"]))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
