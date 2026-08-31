#!/usr/bin/env python3
"""Build a 50k evidence-first ObraSignal prospect universe from public TED awards.

Source: European Commission TED CSV contract-award notices (CC BY 4.0).
This script deliberately prioritizes companies with demonstrated public-works activity.
It does not scrape private/personal contact data and does not fabricate company attributes.
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
from datetime import datetime
from pathlib import Path

OUT = Path(os.environ.get("OUT_DIR", "prospect_output"))
OUT.mkdir(parents=True, exist_ok=True)
RAW = OUT / "raw"
RAW.mkdir(exist_ok=True)

YEARS = [2022, 2021, 2020, 2019]
URL = "https://data.europa.eu/api/hub/store/data/ted-contract-award-notices-{year}.zip"
TARGET = 50_000

# ObraSignal active European scope. BUILD markets get stronger commercial weighting.
BUILD = {
    "PT": 20, "ES": 18, "IT": 18, "FR": 18, "DE": 18, "CH": 17,
    "GB": 17, "NL": 15, "PL": 15,
}
SHARED = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "GR", "HU",
    "IS", "IE", "LV", "LI", "LT", "LU", "MT", "NO", "RO", "SK", "SI", "SE",
}
ACTIVE = set(BUILD) | SHARED

# Header aliases observed across TED CSV generations.
ALIASES = {
    "name": ["WIN_NAME", "WIN_NAME_1", "CONTRACTOR_NAME"],
    "country": ["WIN_COUNTRY_CODE", "WIN_COUNTRY", "CONTRACTOR_COUNTRY_CODE"],
    "town": ["WIN_TOWN", "CONTRACTOR_TOWN"],
    "nuts": ["WIN_NUTS", "WIN_NUTS_CODE"],
    "national_id": ["WIN_NATIONALID", "WIN_NATIONAL_ID", "CONTRACTOR_NATIONALID"],
    "cpv": ["CPV", "CPV_MAIN", "CPV_CODE"],
    "contract_type": ["TYPE_OF_CONTRACT", "CONTRACT_TYPE"],
    "buyer_country": ["ISO_COUNTRY_CODE", "CAE_COUNTRY_CODE", "BUYER_COUNTRY_CODE"],
    "buyer_name": ["CAE_NAME", "BUYER_NAME"],
    "value": ["VALUE_EURO", "AWARD_VALUE_EURO", "VALUE"],
    "award_date": ["DT_AWARD", "AWARD_DATE"],
    "dispatch_date": ["DT_DISPATCH", "PUBLICATION_DATE"],
    "sme": ["B_CONTRACTOR_SME", "WIN_SME", "SME"],
    "url": ["TED_NOTICE_URL", "NOTICE_URL", "URL"],
    "notice": ["ID_NOTICE_CAN", "NOTICE_ID", "ID_NOTICE"],
}

LEGAL_NOISE = {
    "ltd", "limited", "llp", "plc", "sa", "sas", "sasu", "sarl", "gmbh", "ag", "kg",
    "bv", "nv", "oy", "oyj", "ab", "as", "aps", "srl", "spa", "snc", "sc", "sl", "slu",
    "lda", "unipessoal", "sp", "zoo", "kft", "sro", "doo", "d.o.o", "a.s", "s.a", "s.l",
}


def norm_text(s: str) -> str:
    s = (s or "").strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def loose_name(s: str) -> str:
    parts = norm_text(s).split()
    while parts and parts[-1].replace(".", "") in LEGAL_NOISE:
        parts.pop()
    return " ".join(parts)


def pick(row: dict[str, str], field: str) -> str:
    for k in ALIASES[field]:
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def parse_float(s: str) -> float:
    if not s:
        return 0.0
    s = s.strip().replace("\u00a0", "").replace(" ", "")
    # TED numeric exports are normally dot-decimal; tolerate European comma decimal.
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        v = float(s)
        if v < 0 or v > 1e12:
            return 0.0
        return v
    except Exception:
        return 0.0


def year_from_date(s: str, fallback: int) -> int:
    if not s:
        return fallback
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).year
        except Exception:
            pass
    m = re.search(r"(20\d{2})", s)
    return int(m.group(1)) if m else fallback


def download(year: int) -> Path | None:
    dest = RAW / f"ted-contract-award-notices-{year}.zip"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest
    url = URL.format(year=year)
    print(f"Downloading {url}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ObraSignal-prospect-research/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            if dest.stat().st_size < 1000:
                raise RuntimeError("download unexpectedly small")
            return dest
        except Exception as e:
            print(f"Download failed {year} attempt {attempt+1}: {e}", file=sys.stderr, flush=True)
            if dest.exists():
                dest.unlink()
            time.sleep(4 * (attempt + 1))
    return None


def iter_rows(zpath: Path):
    with zipfile.ZipFile(zpath) as zf:
        members = [m for m in zf.namelist() if m.lower().endswith((".csv", ".txt"))]
        if not members:
            raise RuntimeError(f"No CSV member in {zpath}")
        for member in members:
            print(f"Reading {zpath.name}:{member}", flush=True)
            with zf.open(member) as raw:
                # TED CSV is UTF-8; replacement keeps malformed legacy rows processable.
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
                first = text.readline()
                if not first:
                    continue
                delimiter = ";" if first.count(";") > first.count(",") else ","
                text.seek(0)
                reader = csv.DictReader(text, delimiter=delimiter)
                if not reader.fieldnames:
                    continue
                reader.fieldnames = [(h or "").strip().upper() for h in reader.fieldnames]
                for row in reader:
                    yield {str(k).strip().upper(): (v or "") for k, v in row.items() if k is not None}


def is_public_works(row: dict[str, str]) -> tuple[bool, str]:
    cpv = re.sub(r"\D", "", pick(row, "cpv"))
    ctype = norm_text(pick(row, "contract_type"))
    if cpv.startswith("45"):
        return True, cpv[:8]
    # TED commonly uses W for works; tolerate English labels.
    if ctype in {"w", "works", "work"} or "work" in ctype:
        return True, cpv[:8]
    return False, cpv[:8]


def score(p: dict) -> float:
    market = BUILD.get(p["country"], 9 if p["country"] in SHARED else 0)
    wins = min(24.0, 5.0 * math.log2(p["award_count"] + 1))
    recency = {2022: 18, 2021: 14, 2020: 9, 2019: 5}.get(p["last_award_year"], 2)
    buyer_div = min(12.0, 3.0 * math.log2(p["buyer_count"] + 1))
    value = min(14.0, max(0.0, math.log10(p["total_awarded_eur"] + 1) * 2.0))
    sme = 5.0 if p["sme_evidence"] == "yes" else 0.0
    identity = 4.0 if p["national_id"] else 0.0
    return round(min(100.0, market + wins + recency + buyer_div + value + sme + identity), 1)


def tier(s: float) -> str:
    if s >= 78: return "A1"
    if s >= 68: return "A2"
    if s >= 56: return "B"
    return "C"


def angle(p: dict) -> str:
    n = p["award_count"]
    buyers = p["buyer_count"]
    if n >= 8 and buyers >= 3:
        return "Já ganha obras públicas com frequência; vender radar contínuo + priorização/go-no-go para ampliar cobertura sem aumentar trabalho manual."
    if n >= 3:
        return "Tem histórico comprovado de adjudicações; vender shortlist personalizada + alertas para encontrar mais concursos semelhantes aos que já ganha."
    return "Tem prova de participação vencedora em obras públicas; oferecer avaliação assistida focada em novas oportunidades aderentes ao histórico real."


def main():
    csv.field_size_limit(min(sys.maxsize, 2_000_000_000))
    prospects: dict[str, dict] = {}
    stats = defaultdict(int)

    for y in YEARS:
        zpath = download(y)
        if not zpath:
            continue
        for row in iter_rows(zpath):
            stats["rows_seen"] += 1
            ok, cpv = is_public_works(row)
            if not ok:
                continue
            stats["works_rows"] += 1
            name = pick(row, "name")
            if not name or len(name) < 2:
                continue
            country = pick(row, "country").upper()[:2]
            if not country:
                country = pick(row, "buyer_country").upper()[:2]
            if country not in ACTIVE:
                continue
            nid = norm_text(pick(row, "national_id")).replace(" ", "")
            nname = norm_text(name)
            if not nname or nname in {"unknown", "not specified", "n a", "na", "-"}:
                continue
            key = f"{country}|id|{nid}" if nid else f"{country}|name|{nname}"
            award_year = year_from_date(pick(row, "award_date") or pick(row, "dispatch_date"), y)
            val = parse_float(pick(row, "value"))
            buyer = pick(row, "buyer_name")
            sme_raw = norm_text(pick(row, "sme"))
            sme_yes = sme_raw in {"y", "yes", "true", "1", "oui", "si"}
            p = prospects.get(key)
            if p is None:
                p = prospects[key] = {
                    "company_name": name.strip(), "normalized_name": loose_name(name),
                    "country": country, "town": pick(row, "town"), "nuts": pick(row, "nuts"),
                    "national_id": pick(row, "national_id"), "award_count": 0,
                    "buyer_names": set(), "total_awarded_eur": 0.0, "max_award_eur": 0.0,
                    "last_award_year": 0, "last_award_date": "", "last_cpv": "",
                    "sme_evidence": "unknown", "evidence_url": "", "notice_id": "",
                    "source_years": set(),
                }
            p["award_count"] += 1
            if buyer:
                p["buyer_names"].add(norm_text(buyer))
            p["total_awarded_eur"] += val
            p["max_award_eur"] = max(p["max_award_eur"], val)
            p["source_years"].add(y)
            if sme_yes:
                p["sme_evidence"] = "yes"
            if award_year >= p["last_award_year"]:
                p["last_award_year"] = award_year
                p["last_award_date"] = pick(row, "award_date") or pick(row, "dispatch_date")
                p["last_cpv"] = cpv
                p["evidence_url"] = pick(row, "url") or p["evidence_url"]
                p["notice_id"] = pick(row, "notice") or p["notice_id"]
                p["town"] = pick(row, "town") or p["town"]
                p["nuts"] = pick(row, "nuts") or p["nuts"]
        print(f"After {y}: {len(prospects):,} unique candidates", flush=True)

    rows = []
    for p in prospects.values():
        p["buyer_count"] = len(p.pop("buyer_names"))
        p["source_years"] = ",".join(map(str, sorted(p["source_years"])))
        p["fit_score"] = score(p)
        p["tier"] = tier(p["fit_score"])
        p["why_fit"] = (
            f"Vencedor comprovado em obras públicas: {p['award_count']} registo(s), "
            f"{p['buyer_count']} comprador(es), último ano {p['last_award_year']}."
        )
        p["outreach_angle"] = angle(p)
        p["recommended_offer"] = "30-day assisted pilot" if p["fit_score"] >= 78 else "21-day ObraSignal Evaluation"
        p["contact_status"] = "needs_public_business_contact_enrichment"
        p["source_dataset"] = "TED CSV contract award notices; European Commission; CC BY 4.0"
        rows.append(p)

    # Avoid obvious duplicate legal-name variants without collapsing companies that have distinct IDs.
    rows.sort(key=lambda r: (r["fit_score"], r["award_count"], r["total_awarded_eur"]), reverse=True)
    selected = []
    seen_loose = set()
    for r in rows:
        loose = (r["country"], r["normalized_name"], norm_text(r["town"]))
        if not r["national_id"] and r["normalized_name"] and loose in seen_loose:
            continue
        seen_loose.add(loose)
        selected.append(r)
        if len(selected) >= TARGET:
            break

    if len(selected) < TARGET:
        print(f"WARNING: only {len(selected):,} qualified unique public-works prospects found", file=sys.stderr)

    fields = [
        "rank", "company_name", "normalized_name", "country", "town", "nuts", "national_id",
        "fit_score", "tier", "award_count", "buyer_count", "last_award_year", "last_award_date",
        "last_cpv", "total_awarded_eur", "max_award_eur", "sme_evidence", "source_years",
        "why_fit", "outreach_angle", "recommended_offer", "contact_status", "evidence_url",
        "notice_id", "source_dataset",
    ]
    outfile = OUT / "obrasignal_prospects_50000.csv"
    with open(outfile, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for i, r in enumerate(selected, 1):
            rr = dict(r); rr["rank"] = i
            w.writerow(rr)

    summary = {
        "generated_utc": datetime.utcnow().isoformat() + "Z",
        "target": TARGET,
        "selected": len(selected),
        "candidate_pool": len(rows),
        "rows_seen": stats["rows_seen"],
        "works_rows": stats["works_rows"],
        "years_attempted": YEARS,
        "countries": dict(sorted((c, sum(1 for r in selected if r["country"] == c)) for c in ACTIVE)),
        "tiers": dict(sorted((t, sum(1 for r in selected if r["tier"] == t)) for t in {"A1","A2","B","C"})),
        "method": "Public-procurement winners; works CPV 45 or contract type Works; active ObraSignal European scope; evidence-first ranking.",
        "privacy": "Public business/procurement data only; no private or personal contact data.",
    }
    (OUT / "obrasignal_prospects_50000_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    if len(selected) < 45_000:
        raise SystemExit("Insufficient qualified universe: fewer than 45,000 rows")


if __name__ == "__main__":
    main()
