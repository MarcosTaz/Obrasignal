#!/usr/bin/env python3
"""Build a large *additional* ObraSignal prospect candidate pool from historical TED awards.

The existing 200k universe was built primarily from 2019-2023. This extractor uses
2006-2018 European Commission TED contract-award CSV data so the downstream merge can
select 100,000 genuinely new legal entities after deduplication against the canonical
200k database. It covers every market configured for ObraSignal, including historical
UK awards.

Only public procurement/business data is processed. No personal contacts are collected.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(os.environ.get("OUT_DIR", "prospect_expansion_output"))
OUT.mkdir(parents=True, exist_ok=True)
RAW = OUT / "raw"
RAW.mkdir(exist_ok=True)

YEARS = list(range(2018, 2005, -1))
URL = "https://data.europa.eu/api/hub/store/data/ted-contract-award-notices-{year}.zip"
TARGET = int(os.environ.get("TARGET", "250000"))

# Exact active European scope used by the current ObraSignal prospect universe.
ACTIVE = {
    "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
    "GB", "GR", "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MT",
    "NL", "NO", "PL", "PT", "RO", "SE", "SI", "SK",
}

# Core = strongest current ObraSignal fit. Adjacent = still procurement-heavy sectors
# where a tender/opportunity radar has clear operational value.
CORE = {
    "45": (24, "construction works"),
    "71": (21, "engineering/architecture"),
    "50": (19, "repair/maintenance"),
    "51": (18, "installation services"),
    "31": (17, "electrical equipment"),
    "32": (15, "telecom/electronic equipment"),
    "43": (15, "construction machinery"),
    "42": (14, "industrial machinery"),
    "44": (14, "construction materials"),
    "90": (13, "environmental/waste services"),
    "65": (11, "utilities"),
}
ADJACENT = {
    "34": (11, "transport equipment"),
    "35": (11, "security/fire/rescue equipment"),
    "38": (10, "laboratory/optical/precision equipment"),
    "39": (9, "furniture/interior equipment"),
    "60": (9, "transport services"),
    "63": (9, "supporting transport services"),
    "72": (10, "IT services"),
    "79": (8, "business/professional services"),
}
CPV = {**CORE, **ADJACENT}

ALIASES = {
    "name": ["WIN_NAME", "WIN_NAME_1", "CONTRACTOR_NAME"],
    "country": ["WIN_COUNTRY_CODE", "WIN_COUNTRY", "CONTRACTOR_COUNTRY_CODE"],
    "town": ["WIN_TOWN", "CONTRACTOR_TOWN"],
    "nuts": ["WIN_NUTS", "WIN_NUTS_CODE"],
    "national_id": ["WIN_NATIONALID", "WIN_NATIONAL_ID", "CONTRACTOR_NATIONALID"],
    "cpv": ["CPV", "CPV_MAIN", "CPV_CODE", "MAIN_CPV_CODE"],
    "contract_type": ["TYPE_OF_CONTRACT", "CONTRACT_TYPE"],
    "buyer_country": ["ISO_COUNTRY_CODE", "CAE_COUNTRY_CODE", "BUYER_COUNTRY_CODE"],
    "buyer_name": ["CAE_NAME", "BUYER_NAME"],
    "value": ["VALUE_EURO", "AWARD_VALUE_EURO", "VALUE", "VALUE_EURO_FIN_1"],
    "award_date": ["DT_AWARD", "AWARD_DATE"],
    "dispatch_date": ["DT_DISPATCH", "PUBLICATION_DATE"],
    "sme": ["B_CONTRACTOR_SME", "WIN_SME", "SME"],
    "url": ["TED_NOTICE_URL", "NOTICE_URL", "URL"],
    "notice": ["ID_NOTICE_CAN", "NOTICE_ID", "ID_NOTICE"],
}

LEGAL = {
    "ltd", "limited", "llp", "plc", "sa", "sas", "sasu", "sarl", "gmbh", "ag",
    "kg", "bv", "nv", "oy", "oyj", "ab", "as", "aps", "srl", "spa", "snc", "sc",
    "sl", "slu", "lda", "unipessoal", "sp", "zoo", "kft", "sro", "doo", "inc", "co",
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").strip())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def loose(s: str) -> str:
    p = norm(s).split()
    while p and p[-1] in LEGAL:
        p.pop()
    return " ".join(p)


def pick(row: dict[str, str], field: str) -> str:
    for k in ALIASES[field]:
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def money(s: str) -> float:
    if not s:
        return 0.0
    s = s.strip().replace("\u00a0", "").replace(" ", "")
    if s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        v = float(s)
        return v if 0 <= v <= 1e12 else 0.0
    except Exception:
        return 0.0


def award_year(s: str, fallback: int) -> int:
    if not s:
        return fallback
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).year
        except Exception:
            pass
    m = re.search(r"(20\d{2}|19\d{2})", s)
    return int(m.group(1)) if m else fallback


def download(year: int) -> Path | None:
    dest = RAW / f"ted-contract-award-notices-{year}.zip"
    if dest.exists() and dest.stat().st_size > 100_000:
        return dest
    req = urllib.request.Request(
        URL.format(year=year),
        headers={"User-Agent": "ObraSignal-prospect-research/3.0"},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as rr, open(dest, "wb") as f:
                while True:
                    block = rr.read(1024 * 1024)
                    if not block:
                        break
                    f.write(block)
            if dest.stat().st_size < 1000:
                raise RuntimeError("download too small")
            return dest
        except Exception as exc:
            print(f"download {year} attempt {attempt + 1}: {exc}", file=sys.stderr)
            if dest.exists():
                dest.unlink()
            time.sleep(3 * (attempt + 1))
    return None


def rows(zip_path: Path):
    with zipfile.ZipFile(zip_path) as zf:
        members = [x for x in zf.namelist() if x.lower().endswith((".csv", ".txt"))]
        for member in members:
            with zf.open(member) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
                first = text.readline()
                if not first:
                    continue
                delim = ";" if first.count(";") > first.count(",") else ","
                text.seek(0)
                reader = csv.DictReader(text, delimiter=delim)
                if not reader.fieldnames:
                    continue
                reader.fieldnames = [(h or "").strip().upper() for h in reader.fieldnames]
                for row in reader:
                    yield {
                        str(k).strip().upper(): (v or "")
                        for k, v in row.items()
                        if k is not None
                    }


def category(row: dict[str, str]) -> tuple[str, str]:
    code = re.sub(r"\D", "", pick(row, "cpv"))
    pref = code[:2]
    if pref in CPV:
        return pref, code[:8]
    contract_type = norm(pick(row, "contract_type"))
    if contract_type in {"w", "works", "work"} or "work" in contract_type:
        return "45", code[:8]
    return "", code[:8]


def score(p: dict) -> float:
    latest = p["last_award_year"]
    recency = {
        2018: 19, 2017: 18, 2016: 17, 2015: 16, 2014: 14, 2013: 12,
        2012: 10, 2011: 8, 2010: 6, 2009: 4, 2008: 3, 2007: 2, 2006: 1,
    }.get(latest, 0)
    wins = min(23, 5 * math.log2(p["award_count"] + 1))
    buyers = min(12, 3 * math.log2(p["buyer_count"] + 1))
    value = min(11, max(0, math.log10(p["total_awarded_eur"] + 1) * 1.55))
    sme = 5 if p["sme_evidence"] == "yes" else 0
    ident = 4 if p["national_id"] else 0
    category_weight = max((CPV[x][0] for x in p["category_prefixes"]), default=0)
    core_bonus = 8 if any(x in CORE for x in p["category_prefixes"]) else 0
    return round(min(100, recency + wins + buyers + value + sme + ident + category_weight + core_bonus), 1)


def tier(s: float) -> str:
    if s >= 78:
        return "A1"
    if s >= 68:
        return "A2"
    if s >= 54:
        return "B"
    return "C"


def main() -> None:
    csv.field_size_limit(min(sys.maxsize, 2_000_000_000))
    prospects: dict[str, dict] = {}
    stats = defaultdict(int)
    years_loaded: list[int] = []

    for year in YEARS:
        zp = download(year)
        if not zp:
            continue
        years_loaded.append(year)
        for row in rows(zp):
            stats["rows_seen"] += 1
            pref, cpv = category(row)
            if not pref:
                continue
            stats["relevant_rows"] += 1
            name = pick(row, "name")
            if not name or len(name) < 2:
                continue
            country = (pick(row, "country").upper()[:2] or pick(row, "buyer_country").upper()[:2])
            if country not in ACTIVE:
                continue
            nid = norm(pick(row, "national_id")).replace(" ", "")
            nn = norm(name)
            if not nn or nn in {"unknown", "not specified", "n a", "na", "-"}:
                continue
            key = f"{country}|id|{nid}" if nid else f"{country}|name|{nn}"
            ay = award_year(pick(row, "award_date") or pick(row, "dispatch_date"), year)
            val = money(pick(row, "value"))
            buyer = pick(row, "buyer_name")
            sm = norm(pick(row, "sme"))
            p = prospects.get(key)
            if p is None:
                p = prospects[key] = {
                    "company_name": name.strip(),
                    "normalized_name": loose(name),
                    "country": country,
                    "town": pick(row, "town"),
                    "nuts": pick(row, "nuts"),
                    "national_id": pick(row, "national_id"),
                    "award_count": 0,
                    "buyers": set(),
                    "total_awarded_eur": 0.0,
                    "max_award_eur": 0.0,
                    "last_award_year": 0,
                    "last_award_date": "",
                    "last_cpv": "",
                    "sme_evidence": "unknown",
                    "evidence_url": "",
                    "notice_id": "",
                    "source_years": set(),
                    "category_prefixes": set(),
                }
            p["award_count"] += 1
            p["total_awarded_eur"] += val
            p["max_award_eur"] = max(p["max_award_eur"], val)
            p["source_years"].add(year)
            p["category_prefixes"].add(pref)
            if buyer:
                p["buyers"].add(norm(buyer))
            if sm in {"y", "yes", "true", "1", "oui", "si"}:
                p["sme_evidence"] = "yes"
            if ay >= p["last_award_year"]:
                p["last_award_year"] = ay
                p["last_award_date"] = pick(row, "award_date") or pick(row, "dispatch_date")
                p["last_cpv"] = cpv
                p["evidence_url"] = pick(row, "url") or p["evidence_url"]
                p["notice_id"] = pick(row, "notice") or p["notice_id"]
                p["town"] = pick(row, "town") or p["town"]
                p["nuts"] = pick(row, "nuts") or p["nuts"]
        print(year, "unique", len(prospects), flush=True)

    output = []
    for p in prospects.values():
        p["buyer_count"] = len(p.pop("buyers"))
        p["source_years"] = ",".join(map(str, sorted(p["source_years"])))
        cats = sorted(p["category_prefixes"])
        p["procurement_categories"] = ";".join(f"{x}:{CPV[x][1]}" for x in cats)
        p["fit_family"] = "core" if any(x in CORE for x in cats) else "adjacent"
        p["fit_score"] = score(p)
        p["tier"] = tier(p["fit_score"])
        p["why_fit"] = (
            f"Historical public-procurement winner: {p['award_count']} award record(s), "
            f"{p['buyer_count']} buyer(s), latest {p['last_award_year']}; "
            f"categories {p['procurement_categories']}."
        )
        p["contact_status"] = "needs_current_business_verification"
        p["source_dataset"] = "TED contract award notices 2006-2018; European Commission; public data"
        p["category_prefixes"] = ";".join(cats)
        output.append(p)

    output.sort(
        key=lambda r: (
            r["fit_family"] == "core",
            r["fit_score"],
            r["last_award_year"],
            r["award_count"],
            r["buyer_count"],
            r["total_awarded_eur"],
        ),
        reverse=True,
    )

    # Guarantee representation from every market with available historical winners,
    # then fill globally by fit. Downstream merge removes existing-200k duplicates.
    by_country = defaultdict(list)
    for r in output:
        by_country[r["country"]].append(r)
    selected: list[dict] = []
    used: set[tuple] = set()

    def uid(r: dict) -> tuple:
        # town is intentionally omitted when a national id exists.
        if r["national_id"]:
            return (r["country"], "id", norm(r["national_id"]).replace(" ", ""))
        return (r["country"], "name", r["normalized_name"], norm(r["town"]))

    floor = min(1000, max(250, TARGET // (len(ACTIVE) * 8)))
    for country in sorted(ACTIVE):
        for r in by_country.get(country, [])[:floor]:
            u = uid(r)
            if u not in used:
                selected.append(r)
                used.add(u)

    for r in output:
        if len(selected) >= TARGET:
            break
        u = uid(r)
        if u not in used:
            selected.append(r)
            used.add(u)

    fields = [
        "rank", "company_name", "normalized_name", "country", "town", "nuts", "national_id",
        "fit_score", "tier", "fit_family", "award_count", "buyer_count", "last_award_year",
        "last_award_date", "last_cpv", "procurement_categories", "total_awarded_eur",
        "max_award_eur", "sme_evidence", "source_years", "evidence_url", "notice_id",
        "why_fit", "contact_status", "source_dataset",
    ]
    csv_path = OUT / "obrasignal_expansion_candidates.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, r in enumerate(selected, 1):
            q = dict(r)
            q["rank"] = i
            w.writerow({k: q.get(k, "") for k in fields})

    tiers = defaultdict(int)
    countries = defaultdict(int)
    families = defaultdict(int)
    for r in selected:
        tiers[r["tier"]] += 1
        countries[r["country"]] += 1
        families[r["fit_family"]] += 1
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "target_candidate_pool": TARGET,
        "selected": len(selected),
        "full_candidate_pool": len(output),
        "countries_configured": len(ACTIVE),
        "countries_with_candidates": len(countries),
        "countries": dict(sorted(countries.items())),
        "tiers": dict(tiers),
        "fit_families": dict(families),
        "years_attempted": YEARS,
        "years_loaded": years_loaded,
        "rows_seen": stats["rows_seen"],
        "relevant_rows": stats["relevant_rows"],
        "privacy": "Public procurement/business data only; no private or personal contact data.",
        "merge_note": "Downstream merge must deduplicate against the canonical ObraSignal 200k universe before selecting 100,000 additions.",
    }
    (OUT / "obrasignal_expansion_candidates_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if len(selected) < 120000:
        raise SystemExit(f"Only {len(selected)} historical candidates; below safe merge pool")


if __name__ == "__main__":
    main()
