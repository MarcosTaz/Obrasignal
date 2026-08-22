"""Company profile configuration for ObraSignal."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
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
    "countries": ["PRT"],
    "cpv_prefixes": ["45", "44", "42", "43"],
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
    conn.execute(PROFILE_TABLE)
    conn.commit()
    return conn


def _normalize(text: str) -> str:
    text = (text or "").lower()
    return re.sub(r"\s+", " ", text).strip()


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


def derive_profile(activity: str, base: dict | None = None) -> dict:
    profile = dict(DEFAULT_PROFILE)
    if base:
        profile.update({k: v for k, v in base.items() if v is not None})
    interests = profile.get("contract_interests") or []
    if isinstance(interests, str):
        interests = [interests]
    interests = [str(value).strip() for value in interests if str(value).strip()]
    profile["contract_interests"] = interests
    activity_n = _normalize(" ".join([activity or "", *interests]))
    profile["activity"] = activity or profile.get("activity", "")
    keywords = list(profile.get("keywords") or [])
    cpvs = list(profile.get("cpv_prefixes") or [])
    for _, terms, prefixes in ACTIVITY_RULES:
        if any(term in activity_n for term in terms):
            for term in terms:
                if term not in keywords:
                    keywords.append(term)
            for prefix in prefixes:
                if prefix not in cpvs:
                    cpvs.append(prefix)
    profile["keywords"] = keywords
    profile["cpv_prefixes"] = cpvs
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
            profile = dict(DEFAULT_PROFILE)
            profile.update(raw or {})
            profile["account_id"] = account
            return derive_profile(profile.get("activity", ""), profile)
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


def _bootstrap_saved_profile(account: str) -> None:
    try:
        from account_onboarding import bootstrap_account
        bootstrap_account(account)
    except Exception:
        # Profile persistence must remain successful even if the optional
        # bootstrap is unavailable; the regular sync worker will classify it.
        pass


def save_profile(profile: dict, account_id: str | None = None) -> dict:
    requested_account = account_id or (profile or {}).get("account_id") or "default"
    account = str(requested_account).strip() or "default"
    normalized = dict(DEFAULT_PROFILE)
    normalized.update(profile or {})
    normalized["account_id"] = account
    normalized = derive_profile(normalized.get("activity", ""), normalized)
    validation_profile = dict(normalized)
    validation_profile["countries"] = _normalize_countries(validation_profile.get("countries"))
    errors = validate_company_profile(validation_profile)
    if errors:
        raise ValueError({"code": "INVALID_COMPANY_PROFILE", "errors": errors})

    # Durable persistence is the critical operation. Do not write authenticated
    # account profiles to Render's ephemeral filesystem.
    _persist_profile_db(normalized, account)

    # Never make the authenticated profile POST wait for the potentially
    # expensive first-value classification pass. Persistence is the critical
    # operation; onboarding runs asynchronously so the client can immediately
    # return to the Radar and refresh when the account-scoped decisions exist.
    threading.Thread(
        target=_bootstrap_saved_profile,
        args=(account,),
        name="obrasignal-profile-bootstrap",
        daemon=True,
    ).start()
    return normalized
