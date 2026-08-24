"""CanadaBuys federal construction tender connector.

Official source contract live-validated 2026-08-25:
- CanadaBuys tender-notice open data is federal-only and Open Government Licence;
- all tender files share the same 67-column UTF-8 CSV schema;
- publisher-native procurement category token ``CNST`` means construction;
- ``solicitationNumber-numeroSollicitation`` is the cross-dataset stable identity;
- ``referenceNumber-numeroReference`` is preserved as a notice/source reference but
  is not used as durable identity because CanadaBuys documents that it can vary;
- amendment number/date are publisher-native version information for the same tender;
- New Tender Notices is a cumulative intraday new-notice file refreshed about every
  two hours; Open Tender Notices is the authoritative daily snapshot of tenders open
  for bidding and contains current amendments;
- tender closing timestamps are fixed UTC-05:00, not local Eastern daylight time;
- tender-notice rows do not expose a tender value/currency field, so this connector
  deliberately emits no fabricated value.

The connector uses conditional HTTP requests so repeated runs do not download
unchanged snapshots. New provides low-latency discovery; Open reconciles the active
set and amendment state. Missing Open rows are only closed automatically when their
known deadline has elapsed. A future-dated disappearance is retained as unknown
rather than being falsely called cancelled; a later lifecycle source can resolve it.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import csv
from io import StringIO
import json

import requests

SOURCE = "CA_CANADABUYS"
COUNTRY = "CAN"
NEW_URL = "https://canadabuys.canada.ca/opendata/pub/newTenderNotice-nouvelAvisAppelOffres.csv"
OPEN_URL = "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"
CATALOG_URL = "https://open.canada.ca/data/en/dataset/6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2"
PUBLIC_SITE = "https://canadabuys.canada.ca/en/tender-opportunities"
ATTRIBUTION = "Public Services and Procurement Canada — CanadaBuys"
FIXED_SOURCE_TZ = timezone(timedelta(hours=-5))
HEADERS = {
    "Accept": "text/csv,application/octet-stream;q=0.9,*/*;q=0.1",
    "User-Agent": "ObraSignal CanadaBuys connector/1.0 (+official open-data ingestion)",
}

CSV_FIELDS = (
    "title-titre-eng", "title-titre-fra", "referenceNumber-numeroReference",
    "amendmentNumber-numeroModification", "solicitationNumber-numeroSollicitation",
    "publicationDate-datePublication", "tenderClosingDate-appelOffresDateCloture",
    "amendmentDate-dateModification", "expectedContractStartDate-dateDebutContratPrevue",
    "expectedContractEndDate-dateFinContratPrevue", "tenderStatus-appelOffresStatut-eng",
    "tenderStatus-appelOffresStatut-fra", "gsin-nibs", "gsinDescription-nibsDescription-eng",
    "gsinDescription-nibsDescription-fra", "unspsc", "unspscDescription-eng",
    "unspscDescription-fra", "procurementCategory-categorieApprovisionnement",
    "noticeType-avisType-eng", "noticeType-avisType-fra",
    "procurementMethod-methodeApprovisionnement-eng",
    "procurementMethod-methodeApprovisionnement-fra",
    "selectionCriteria-criteresSelection-eng", "selectionCriteria-criteresSelection-fra",
    "limitedTenderingReason-raisonAppelOffresLimite-eng",
    "limitedTenderingReason-raisonAppelOffresLimite-fra",
    "tradeAgreements-accordsCommerciaux-eng", "tradeAgreements-accordsCommerciaux-fra",
    "regionsOfOpportunity-regionAppelOffres-eng", "regionsOfOpportunity-regionAppelOffres-fra",
    "regionsOfDelivery-regionsLivraison-eng", "regionsOfDelivery-regionsLivraison-fra",
    "contractingEntityName-nomEntitContractante-eng",
    "contractingEntityAddressLine-ligneAdresseEntiteContractante-eng",
    "contractingEntityAddressCity-entiteContractanteAdresseVille-eng",
    "contractingEntityAddressProvince-entiteContractanteAdresseProvince-eng",
    "contractingEntityAddressPostalCode-entiteContractanteAdresseCodePostal",
    "contractingEntityAddressCountry-entiteContractanteAdressePays-eng",
    "contractingEntityName-nomEntitContractante-fra",
    "contractingEntityAddressLine-ligneAdresseEntiteContractante-fra",
    "contractingEntityAddressCity-entiteContractanteAdresseVille-fra",
    "contractingEntityAddressProvince-entiteContractanteAdresseProvince-fra",
    "contractingEntityAddressCountry-entiteContractanteAdressePays-fra",
    "endUserEntitiesName-nomEntitesUtilisateurFinal-eng",
    "endUserEntitiesAddress-adresseEntitesUtilisateurFinal-eng",
    "endUserEntitiesName-nomEntitesUtilisateurFinal-fra",
    "endUserEntitiesAddress-adresseEntitesUtilisateurFinal-fra",
    "contactInfoName-informationsContactNom", "contactInfoEmail-informationsContactCourriel",
    "contactInfoPhone-contactInfoTelephone", "contactInfoFax",
    "contactInfoAddressLine-contactInfoAdresseLigne-eng", "contactInfoCity-contacterInfoVille-eng",
    "contactInfoProvince-contacterInfoProvince-eng", "contactInfoPostalcode",
    "contactInfoCountry-contactInfoPays-eng", "contactInfoAddressLine-contactInfoAdresseLigne-fra",
    "contactInfoCity-contacterInfoVille-fra", "contactInfoProvince-contacterInfoProvince-fra",
    "contactInfoCountry-contactInfoPays-fra", "noticeURL-URLavis-eng", "noticeURL-URLavis-fra",
    "attachment-piecesJointes-eng", "attachment-piecesJointes-fra",
    "tenderDescription-descriptionAppelOffres-eng",
    "tenderDescription-descriptionAppelOffres-fra",
)


def _text(value):
    return str(value or "").strip()


def _tokens(value):
    out = []
    for line in _text(value).replace("\r", "\n").split("\n"):
        token = line.strip().lstrip("*").strip()
        if token and token not in out:
            out.append(token)
    return out


def _is_construction(row):
    return "CNST" in _tokens(row.get("procurementCategory-categorieApprovisionnement"))


def _source_datetime(value):
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=FIXED_SOURCE_TZ)
    return parsed.astimezone(timezone.utc)


def _utc(value):
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _deadline(row):
    return _source_datetime(row.get("tenderClosingDate-appelOffresDateCloture"))


def _identity(row):
    return _text(row.get("solicitationNumber-numeroSollicitation"))


def _state(row):
    external_id = _identity(row)
    reference = _text(row.get("referenceNumber-numeroReference"))
    deadline = _deadline(row)
    if not external_id:
        raise RuntimeError(f"{SOURCE} construction row missing solicitation number; cursor not advanced")
    if not reference:
        raise RuntimeError(f"{SOURCE} construction row missing reference number; cursor not advanced")
    if deadline is None:
        raise RuntimeError(f"{SOURCE} construction row missing/invalid closing timestamp; cursor not advanced")

    categories = _tokens(row.get("procurementCategory-categorieApprovisionnement"))
    if "CNST" not in categories:
        raise RuntimeError(f"{SOURCE} non-construction row passed construction gate; cursor not advanced")

    return {
        "external_id": external_id,
        "reference_number": reference,
        "amendment_number": _text(row.get("amendmentNumber-numeroModification")),
        "amendment_date": _text(row.get("amendmentDate-dateModification")),
        "publication_date": _text(row.get("publicationDate-datePublication")),
        "deadline": _utc(deadline),
        "source_status": _text(row.get("tenderStatus-appelOffresStatut-eng")),
        "title": _text(row.get("title-titre-eng")) or _text(row.get("title-titre-fra")),
        "description": _text(row.get("tenderDescription-descriptionAppelOffres-eng")) or _text(row.get("tenderDescription-descriptionAppelOffres-fra")),
        "buyer": _text(row.get("contractingEntityName-nomEntitContractante-eng")) or _text(row.get("contractingEntityName-nomEntitContractante-fra")),
        "buyer_city": _text(row.get("contractingEntityAddressCity-entiteContractanteAdresseVille-eng")),
        "buyer_province": _text(row.get("contractingEntityAddressProvince-entiteContractanteAdresseProvince-eng")),
        "regions_of_opportunity": _tokens(row.get("regionsOfOpportunity-regionAppelOffres-eng")),
        "regions_of_delivery": _tokens(row.get("regionsOfDelivery-regionsLivraison-eng")),
        "categories": categories,
        "unspsc": _tokens(row.get("unspsc")),
        "gsin": _tokens(row.get("gsin-nibs")),
        "notice_type": _text(row.get("noticeType-avisType-eng")),
        "procurement_method": _text(row.get("procurementMethod-methodeApprovisionnement-eng")),
        "selection_criteria": _text(row.get("selectionCriteria-criteresSelection-eng")),
        "trade_agreements": _tokens(row.get("tradeAgreements-accordsCommerciaux-eng")),
        "expected_contract_start": _text(row.get("expectedContractStartDate-dateDebutContratPrevue")),
        "expected_contract_end": _text(row.get("expectedContractEndDate-dateFinContratPrevue")),
        "notice_url": _text(row.get("noticeURL-URLavis-eng")) or _text(row.get("noticeURL-URLavis-fra")),
        "attachment": _text(row.get("attachment-piecesJointes-eng")) or _text(row.get("attachment-piecesJointes-fra")),
        "was_visible": False,
    }


def _observation(state, *, actionable=True, lifecycle_status="open", lifecycle_reason="publisher_open", lifecycle_only=False):
    unspsc = list(state.get("unspsc") or [])
    place_parts = list(state.get("regions_of_delivery") or []) or list(state.get("regions_of_opportunity") or [])
    if not place_parts:
        for value in (state.get("buyer_city"), state.get("buyer_province")):
            value = _text(value)
            if value and value not in place_parts:
                place_parts.append(value)
    row = {
        "source": SOURCE,
        "external_id": _text(state.get("external_id")),
        "title": _text(state.get("title")),
        "description": _text(state.get("description")),
        "buyer": _text(state.get("buyer")),
        "country": COUNTRY,
        "cpv": "",
        "taxonomy": "UNSPSC" if unspsc else "",
        "category_code": unspsc[0] if unspsc else "",
        "cpv_codes": [],
        "value": "",
        "currency": "",
        "deadline": _text(state.get("deadline")),
        "publication_date": _text(state.get("publication_date")),
        "published_at": None,
        "source_updated_at": None,
        "url": _text(state.get("notice_url")) or PUBLIC_SITE,
        "market": "GLOBAL",
        "place": " | ".join(place_parts),
        "source_status": _text(state.get("source_status")),
        "source_phase": "notice",
        "signal_type": "TENDER",
        "procurement_method": _text(state.get("procurement_method")),
        "contract_type": "works",
        "source_reference": _text(state.get("reference_number")),
        "notice_identifier": _text(state.get("reference_number")),
        "procedure_reference": _text(state.get("external_id")),
        "amendment_number": _text(state.get("amendment_number")),
        "amendment_date": _text(state.get("amendment_date")),
        "notice_type": _text(state.get("notice_type")),
        "selection_criteria": _text(state.get("selection_criteria")),
        "procurement_categories": list(state.get("categories") or []),
        "unspsc_codes": unspsc,
        "gsin_codes": list(state.get("gsin") or []),
        "regions_of_opportunity": list(state.get("regions_of_opportunity") or []),
        "regions_of_delivery": list(state.get("regions_of_delivery") or []),
        "trade_agreements": list(state.get("trade_agreements") or []),
        "expected_contract_start": _text(state.get("expected_contract_start")),
        "expected_contract_end": _text(state.get("expected_contract_end")),
        "attachment": _text(state.get("attachment")),
        "attribution": ATTRIBUTION,
        "source_catalog_url": CATALOG_URL,
        "source_api_url": OPEN_URL,
        "is_actionable": bool(actionable),
        "lifecycle_status": lifecycle_status,
        "lifecycle_reason": lifecycle_reason,
    }
    if lifecycle_only:
        row["_lifecycle_only"] = True
    return row


def _parse_csv(content):
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"{SOURCE} CSV is not UTF-8; cursor not advanced") from exc
    else:
        text = str(content or "")
    reader = csv.DictReader(StringIO(text, newline=""))
    fields = tuple(reader.fieldnames or ())
    if fields != CSV_FIELDS:
        raise RuntimeError(f"{SOURCE} CSV schema drift: expected 67 publisher columns; cursor not advanced")
    rows = list(reader)
    if any(None in row for row in rows):
        raise RuntimeError(f"{SOURCE} malformed CSV row exceeds publisher schema; cursor not advanced")
    return rows


@dataclass
class CanadaBuysCursor:
    tracked: dict
    etag_new: str = ""
    modified_new: str = ""
    etag_open: str = ""
    modified_open: str = ""
    open_observed_at: str = ""

    @classmethod
    def empty(cls):
        return cls(tracked={})

    @classmethod
    def decode(cls, value):
        if value in (None, ""):
            return cls.empty()
        try:
            payload = json.loads(value)
        except Exception as exc:
            raise RuntimeError(f"invalid {SOURCE} cursor; cursor not advanced") from exc
        if not isinstance(payload, dict) or int(payload.get("version") or 0) != 1:
            raise RuntimeError(f"invalid {SOURCE} cursor version; cursor not advanced")
        tracked = payload.get("tracked") or {}
        if not isinstance(tracked, dict):
            raise RuntimeError(f"invalid {SOURCE} cursor tracked state; cursor not advanced")
        return cls(
            tracked=deepcopy(tracked),
            etag_new=_text(payload.get("etag_new")),
            modified_new=_text(payload.get("modified_new")),
            etag_open=_text(payload.get("etag_open")),
            modified_open=_text(payload.get("modified_open")),
            open_observed_at=_text(payload.get("open_observed_at")),
        )

    def encode(self):
        return json.dumps({
            "version": 1,
            "tracked": self.tracked,
            "etag_new": self.etag_new,
            "modified_new": self.modified_new,
            "etag_open": self.etag_open,
            "modified_open": self.modified_open,
            "open_observed_at": self.open_observed_at,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class CanadaBuysConnector:
    def __init__(self, *, session=None):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)

    def _download(self, url, *, etag="", modified=""):
        headers = dict(HEADERS)
        if etag:
            headers["If-None-Match"] = etag
        if modified:
            headers["If-Modified-Since"] = modified
        response = self.session.get(url, headers=headers, timeout=60)
        if response.status_code == 304:
            return None, etag, modified
        response.raise_for_status()
        content = response.content
        if not content:
            raise RuntimeError(f"{SOURCE} {url} returned empty body; cursor not advanced")
        return _parse_csv(content), _text(response.headers.get("ETag")), _text(response.headers.get("Last-Modified"))

    def fetch_incremental(self, *, watermark=None, now=None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        now = now.astimezone(timezone.utc)
        cursor = CanadaBuysCursor.decode(watermark)

        new_rows, etag_new, modified_new = self._download(
            NEW_URL, etag=cursor.etag_new, modified=cursor.modified_new
        )
        open_rows, etag_open, modified_open = self._download(
            OPEN_URL, etag=cursor.etag_open, modified=cursor.modified_open
        )

        current = deepcopy(cursor.tracked)
        observations = []

        # New is cumulative intraday and only accelerates discovery. It never closes.
        if new_rows is not None:
            seen_new = set()
            for raw in new_rows:
                if not _is_construction(raw):
                    continue
                state = _state(raw)
                external_id = state["external_id"]
                if external_id in seen_new:
                    raise RuntimeError(f"{SOURCE} duplicate construction identity in New file; cursor not advanced")
                seen_new.add(external_id)
                if state["source_status"].lower() != "open":
                    continue
                if _source_datetime(state["deadline"]) <= now:
                    continue
                state["was_visible"] = True
                previous = current.get(external_id)
                if previous != state:
                    observations.append(_observation(state, lifecycle_reason="new_intraday_notice"))
                current[external_id] = state

        # Open is the authoritative active snapshot and amendment reconciler.
        if open_rows is not None:
            open_states = {}
            for raw in open_rows:
                if not _is_construction(raw):
                    continue
                state = _state(raw)
                external_id = state["external_id"]
                if external_id in open_states:
                    raise RuntimeError(f"{SOURCE} duplicate construction identity in Open snapshot; cursor not advanced")
                if state["source_status"].lower() != "open":
                    raise RuntimeError(f"{SOURCE} Open snapshot contains non-open tender; cursor not advanced")
                state["was_visible"] = True
                open_states[external_id] = state

            next_tracked = {}
            for external_id in sorted(set(current) | set(open_states)):
                previous = current.get(external_id)
                state = open_states.get(external_id)
                if state is not None:
                    deadline = _source_datetime(state["deadline"])
                    if deadline <= now:
                        # Publisher can transiently retain just-closed rows in a daily snapshot.
                        if isinstance(previous, dict) and previous.get("was_visible"):
                            observations.append(_observation(
                                state, actionable=False, lifecycle_status="expired",
                                lifecycle_reason="deadline_elapsed", lifecycle_only=True,
                            ))
                        continue
                    next_tracked[external_id] = state
                    if previous != state:
                        observations.append(_observation(state, lifecycle_reason="open_snapshot_state"))
                    continue

                if not isinstance(previous, dict):
                    continue
                deadline = _source_datetime(previous.get("deadline"))
                if deadline is not None and deadline <= now:
                    observations.append(_observation(
                        previous, actionable=False, lifecycle_status="expired",
                        lifecycle_reason="missing_from_open_snapshot_after_deadline",
                        lifecycle_only=True,
                    ))
                else:
                    # A future-dated disappearance may be cancellation, upstream lag, or
                    # a source anomaly. Preserve it but never fabricate a terminal cause.
                    retained = deepcopy(previous)
                    retained["was_visible"] = True
                    next_tracked[external_id] = retained
            current = next_tracked

        next_cursor = CanadaBuysCursor(
            tracked=current,
            etag_new=etag_new,
            modified_new=modified_new,
            etag_open=etag_open,
            modified_open=modified_open,
            open_observed_at=_utc(now) if open_rows is not None else cursor.open_observed_at,
        )
        return observations, next_cursor.encode()


def fetch_canadabuys_tenders(*, watermark=None, session=None, now=None):
    return CanadaBuysConnector(session=session).fetch_incremental(watermark=watermark, now=now)
