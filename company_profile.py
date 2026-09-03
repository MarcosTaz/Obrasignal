"""Company profile configuration for ObraSignal."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from company_profile_validation import validate_company_profile
from unified_company_profile import normalize_company_profile

DEFAULT_PROFILE = {
    "account_id": "default",
    "name": "",
    "activity": "",
    "contract_interests": [],
    "coverage_mode": "portugal",
    "keywords": [],
    "manual_keywords": [],
    "inferred_keywords": [],
    "countries": ["PRT"],
    "cpv_prefixes": [],
    "manual_cpv_prefixes": [],
    "inferred_cpv_prefixes": [],
    "min_value": None,
    "max_value": None,
    "economic_min_score": 60,
    "min_deadline_days": None,
    "max_deadline_days": None,
    "preferred_procedure_types": [],
    "excluded_procedure_types": [],
    "exclude_keywords": [],
    "regions": [],
    "geographic_radius_km": None,
    "services": [],
    "capability_tags": [],
    "project_scales": [],
    "certifications": [],
    "hard_exclusions": [],
}

ACTIVITY_RULES = [
    # Do not infer the whole works family (45) for a specialist metal profile:
    # that made unrelated rehabilitation and electrical lots look compatible.
    ("metalomecanica", ["metalomecânica", "metalomecanica", "estrutura metálica", "estruturas metálicas", "serralharia", "steel", "aço", "aco"], ["4522", "443"]),
    ("construcao", ["construção", "construcao", "empreitada", "obras", "construction", "reabilitação", "reabilitacao"], ["45"]),
    ("coberturas", ["cobertura", "coberturas", "telhado", "roof", "fachada", "pavilhão", "pavilhao"], ["45", "44"]),
    ("armazens", ["armazém", "armazem", "warehouse", "pavilhão", "pavilhao", "industrial"], ["45", "44"]),
    ("eletricidade", ["instalação elétrica", "instalações elétricas", "eletricidade", "iluminação", "electricidade"], ["4531", "315"]),
    ("pintura", ["pintura", "pinturas", "acabamento", "acabamentos"], ["4544"]),
    ("climatizacao", ["climatização", "avac", "aquecimento", "ventilação", "ar condicionado"], ["4533", "425"]),
    ("canalizacao", ["canalização", "redes de água", "saneamento", "tubagens"], ["4533", "4416"]),
    ("manutencao", ["manutenção de edifícios", "manutenção industrial", "reparação", "conservação"], ["50", "45"]),
    ("limpeza", ["limpeza de edifícios", "serviços de limpeza", "higienização"], ["9091"]),
    ("tecnologia", ["software", "desenvolvimento de aplicações", "serviços informáticos", "cibersegurança"], ["48", "72"]),
]

_COUNTRY_ALIASES = {
    "PT": "PRT", "ES": "ESP", "FR": "FRA", "DE": "DEU", "IT": "ITA",
    "BE": "BEL", "NL": "NLD", "LU": "LUX", "IE": "IRL", "AT": "AUT",
    "PL": "POL", "CZ": "CZE", "DK": "DNK", "SE": "SWE", "FI": "FIN",
    "NO": "NOR", "GB": "GBR",
}

# Older releases stored inferred terms and explicit user criteria in the same
# arrays. These sets let us migrate old documents conservatively: known inference
# artefacts are rebuilt from the *current* activity, while unknown/custom values
# are preserved as manual user criteria.
_KNOWN_INFERRED_TERMS = {str(term).strip() for _, terms, _ in ACTIVITY_RULES for term in terms}
_KNOWN_INFERRED_CPVS = {str(prefix).strip() for _, _, prefixes in ACTIVITY_RULES for prefix in prefixes}
_LEGACY_BROAD_DEFAULT_CPVS = {"45", "44", "42", "43"}

PROFILE_TABLE = """
CREATE TABLE IF NOT EXISTS company_profiles (
    account_id TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _db_path() -> str:
    return os.getenv("OBRASIGNAL_DB", str(Path(__file__).with_name("obrasignal.db")))


def _profile_db():
    conn = sqlite3.connect(_db_path(), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='company_profiles'").fetchone()
    if not exists:
        ensure_profile_table(conn)
    return conn


def ensure_profile_table(conn):
    conn.execute(PROFILE_TABLE)
    conn.commit()


def _normalize(text: str) -> str:
    text = (text or "").lower()
    return re.sub(r"\s+", " ", text).strip()


def _unique(values) -> list[str]:
    out = []
    for value in values or []:
        token = str(value).strip()
        if token and token not in out:
            out.append(token)
    return out


def _normalize_countries(values) -> list[str]:
    normalized = []
    for value in values or []:
        code = str(value).strip().upper()
        if not code:
            continue
        code = _COUNTRY_ALIASES.get(code, code)
        if code not in normalized:
            normalized.append(code)
    return normalized


def _normalize_optional_number(value):
    """Accept JSON/form numeric strings without persisting a second type."""
    if value in (None, ""):
        return None
    if isinstance(value, str):
        token = value.strip().replace(" ", "")
        if "," in token and "." not in token:
            token = token.replace(",", ".")
        try:
            return float(token)
        except ValueError:
            return value  # validation returns the existing field-specific error
    return value


def _legacy_manual_keywords(profile: dict) -> list[str]:
    if "manual_keywords" in profile:
        return _unique(profile.get("manual_keywords"))
    return [
        value for value in _unique(profile.get("keywords"))
        if value not in _KNOWN_INFERRED_TERMS
    ]


def _legacy_manual_cpvs(profile: dict) -> list[str]:
    if "manual_cpv_prefixes" in profile:
        return _unique(profile.get("manual_cpv_prefixes"))
    return [
        value for value in _unique(profile.get("cpv_prefixes"))
        if value not in _KNOWN_INFERRED_CPVS and value not in _LEGACY_BROAD_DEFAULT_CPVS
    ]


def derive_profile(activity: str, base: dict | None = None) -> dict:
    """Derive current criteria without carrying stale inference across edits.

    Manual criteria and inferred criteria have separate provenance. The public
    compatibility fields ``keywords`` and ``cpv_prefixes`` remain the union used
    by existing matchers, but inferred values are rebuilt from the current
    activity + contract interests on every load/save.
    """
    supplied = dict(base or {})
    profile = dict(DEFAULT_PROFILE)
    profile.update({k: v for k, v in supplied.items() if v is not None})
    interests = profile.get("contract_interests") or []
    if isinstance(interests, str):
        interests = [interests]
    interests = _unique(interests)
    profile["contract_interests"] = interests
    activity_value = activity or profile.get("activity", "")
    activity_n = _normalize(" ".join([activity_value, *interests]))
    profile["activity"] = activity_value

    manual_keywords = _legacy_manual_keywords(supplied or profile)
    manual_cpvs = _legacy_manual_cpvs(supplied or profile)
    inferred_keywords = []
    inferred_cpvs = []
    for _, terms, prefixes in ACTIVITY_RULES:
        if any(term in activity_n for term in terms):
            inferred_keywords.extend(terms)
            inferred_cpvs.extend(prefixes)

    profile["manual_keywords"] = _unique(manual_keywords)
    profile["inferred_keywords"] = _unique(inferred_keywords)
    profile["keywords"] = _unique([*profile["manual_keywords"], *profile["inferred_keywords"]])
    profile["manual_cpv_prefixes"] = _unique(manual_cpvs)
    profile["inferred_cpv_prefixes"] = _unique(inferred_cpvs)
    profile["cpv_prefixes"] = _unique([*profile["manual_cpv_prefixes"], *profile["inferred_cpv_prefixes"]])
    profile["countries"] = _normalize_countries(profile.get("countries")) or ["PRT"]
    return normalize_company_profile(profile)


def _legacy_profile_path(account_id: str | None = None) -> str:
    account = str(account_id or "default").strip() or "default"
    if account == "default":
        return (
            os.getenv("OBRASIGNAL_PROFILE")
            or os.getenv("OBRASIGNAL_PROFILE_FILE")
            or "company_profile.json"
        )
    root = os.getenv("OBRASIGNAL_PROFILE_DIR", "profiles")
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", account)
    return os.path.join(root, f"{safe}.json")


def _load_legacy_profile(account: str) -> dict | None:
    path = _legacy_profile_path(account)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        profile = dict(DEFAULT_PROFILE)
        profile.update(raw or {})
        profile["account_id"] = account
        return derive_profile(profile.get("activity", ""), profile)
    except (FileNotFoundError, OSError, TypeError, ValueError):
        if account == "default":
            raw = os.getenv("OBRASIGNAL_PROFILE_JSON", "").strip()
            if raw:
                try:
                    profile = dict(DEFAULT_PROFILE)
                    profile.update(json.loads(raw))
                    profile["account_id"] = account
                    return derive_profile(profile.get("activity", ""), profile)
                except (TypeError, ValueError):
                    pass
        return None


def load_profile(account_id: str | None = None) -> dict:
    account = str(account_id or "default").strip() or "default"
    conn = _profile_db()
    try:
        row = conn.execute("SELECT profile_json FROM company_profiles WHERE account_id=?", (account,)).fetchone()
    finally:
        conn.close()

    if row:
        try:
            raw = json.loads(row["profile_json"])
            raw = dict(raw or {})
            raw["account_id"] = account
            return derive_profile(raw.get("activity", ""), raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    # Backward compatibility for any profile written by an older deployment.
    # Import it once into durable storage instead of continuing to depend on
    # the Render filesystem.
    legacy = _load_legacy_profile(account)
    if legacy is not None:
        _persist_profile_db(legacy, account)
        return legacy
    profile = dict(DEFAULT_PROFILE)
    profile["account_id"] = account
    return profile


def _persist_profile_db(profile: dict, account: str) -> None:
    from datetime import datetime, timezone
    conn = _profile_db()
    try:
        conn.execute(
            """INSERT INTO company_profiles(account_id, profile_json, updated_at)
               VALUES(?, ?, ?)
               ON CONFLICT(account_id) DO UPDATE SET profile_json=excluded.profile_json, updated_at=excluded.updated_at""",
            (account, json.dumps(profile, ensure_ascii=False, separators=(",", ":")), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def save_profile(profile: dict, account_id: str | None = None) -> dict:
    requested_account = account_id or (profile or {}).get("account_id") or "default"
    account = str(requested_account).strip() or "default"
    supplied = dict(profile or {})
    normalized = dict(DEFAULT_PROFILE)
    normalized.update(supplied)

    # The flattened compatibility fields are also a public write contract. If a
    # caller explicitly supplies keywords/CPVs without provenance fields, treat
    # them as manual customer criteria before defaults introduce empty manual_*
    # arrays. Otherwise explicit CPVs can silently disappear during derivation.
    if "manual_keywords" not in supplied and "keywords" in supplied:
        normalized["manual_keywords"] = _unique(supplied.get("keywords"))
    if "manual_cpv_prefixes" not in supplied and "cpv_prefixes" in supplied:
        normalized["manual_cpv_prefixes"] = _unique(supplied.get("cpv_prefixes"))

    normalized["account_id"] = account
    normalized["min_value"] = _normalize_optional_number(normalized.get("min_value"))
    normalized["max_value"] = _normalize_optional_number(normalized.get("max_value"))
    normalized = derive_profile(normalized.get("activity", ""), normalized)
    normalized["countries"] = _normalize_countries(normalized.get("countries")) or ["PRT"]
    errors = validate_company_profile(normalized)
    if errors:
        raise ValueError({"code": "INVALID_COMPANY_PROFILE", "errors": errors})

    # Durable persistence is the critical operation. Do not write authenticated
    # account profiles to Render's ephemeral filesystem.
    _persist_profile_db(normalized, account)
    # A successfully validated and durably persisted company profile is the
    # authoritative profile_ready event for the evaluation lifecycle.
    try:
        from account_registry import ensure_account
        from evaluation_policy import record_evaluation_event
        conn = _profile_db()
        try:
            ensure_account(conn, account)
            record_evaluation_event(conn, account, 'profile_ready')
        finally:
            conn.close()
    except Exception:
        # Profile persistence must not fail because evaluation telemetry fails.
        # The missing event remains observable/recoverable via billing status.
        pass

    return normalized
