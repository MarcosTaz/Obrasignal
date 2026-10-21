"""Source-native UK3 planned-procurement normalization for Find a Tender OCDS.

This module deliberately handles UK3 only. Find a Tender publishes the Procurement
Act notice type in ``planning.documents[].noticeType`` and UK3 edits remain linked by
the same OCID. That gives a stable logical identity without inferring lifecycle from
free text. UK2 preliminary market engagement is intentionally deferred because more
than one engagement notice can exist for a procurement and the OCDS output omits the
``previousNotice`` edit link needed for conservative logical deduplication.
"""
from __future__ import annotations

from datetime import datetime, timezone


SOURCE = "UK_PROCUREMENT"
COUNTRY = "GBR"
UK3_NOTICE_TYPE = "UK3"
UK3_DOCUMENT_TYPE = "plannedProcurementNotice"
UK_PROCUREMENT_ACT_ID = "2023/54"
UK_PROCUREMENT_ACT_SCHEME = "UKPGA"
FTS_LICENSE = "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
FTS_ATTRIBUTION = "Find a Tender service — UK Cabinet Office"


class UKPlanningSchemaError(RuntimeError):
    """Raised when a UK3 release cannot be represented without guessing."""


def _text(value):
    return "" if value is None else str(value).strip()


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _dt(value):
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UKPlanningSchemaError(f"invalid Find a Tender datetime: {text!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cpv_entries(items):
    entries = []
    seen = set()
    for item in _list(items):
        if not isinstance(item, dict):
            continue
        classifications = []
        primary = item.get("classification")
        if isinstance(primary, dict):
            classifications.append(primary)
        classifications.extend(
            row for row in _list(item.get("additionalClassifications")) if isinstance(row, dict)
        )
        for classification in classifications:
            scheme = _text(classification.get("scheme")).upper().replace("-", "")
            code = _text(classification.get("id"))
            if scheme not in {"CPV", "CPV2008"} or not code or code in seen:
                continue
            seen.add(code)
            entries.append({
                "id": code,
                "description": _text(classification.get("description")),
            })
    return entries


def _is_construction(tender):
    if _text(tender.get("mainProcurementCategory")).lower() == "works":
        return True
    return any(row["id"].startswith("45") for row in _cpv_entries(tender.get("items")))


def _uk3_document(release):
    release_id = _text(release.get("id"))
    planning = _dict(release.get("planning"))
    matches = [
        row
        for row in _list(planning.get("documents"))
        if isinstance(row, dict) and _text(row.get("noticeType")).upper() == UK3_NOTICE_TYPE
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise UKPlanningSchemaError("Find a Tender UK3 release has ambiguous planning document identity")
    document = matches[0]
    if not release_id:
        raise UKPlanningSchemaError("Find a Tender UK3 release is missing publisher release id")
    if _text(document.get("id")) != release_id:
        raise UKPlanningSchemaError("Find a Tender UK3 planning document id does not match release id")
    if _text(document.get("documentType")) != UK3_DOCUMENT_TYPE:
        raise UKPlanningSchemaError("Find a Tender UK3 documentType contract changed")
    url = _text(document.get("url"))
    if not url.startswith("https://www.find-tender.service.gov.uk/"):
        raise UKPlanningSchemaError("Find a Tender UK3 official document URL is missing or unsafe")
    return document


def _assert_procurement_act_notice(tender):
    basis = _dict(tender.get("legalBasis"))
    if (
        _text(basis.get("id")) != UK_PROCUREMENT_ACT_ID
        or _text(basis.get("scheme")).upper() != UK_PROCUREMENT_ACT_SCHEME
    ):
        raise UKPlanningSchemaError("Find a Tender UK3 legalBasis is not Procurement Act 2023")


def normalize_uk3_release(release):
    """Return one canonical PROCUREMENT_PLAN, ``None`` for non-UK3/non-construction.

    Logical identity is ``{ocid}:notice:UK3`` rather than the publication-version
    release id. Find a Tender permits UK3 edits but not a second independent UK3 in
    the same procurement sequence, so a corrected publication updates one plan
    instead of manufacturing a new opportunity.
    """
    if not isinstance(release, dict):
        raise UKPlanningSchemaError("Find a Tender release must be an object")

    document = _uk3_document(release)
    if document is None:
        return None

    tags = {_text(tag) for tag in _list(release.get("tag")) if _text(tag)}
    if not tags.intersection({"planning", "planningUpdate"}):
        raise UKPlanningSchemaError("Find a Tender UK3 release is missing planning/planningUpdate tag")

    ocid = _text(release.get("ocid"))
    if not ocid:
        raise UKPlanningSchemaError("Find a Tender UK3 release is missing OCID")

    tender = _dict(release.get("tender"))
    if not tender:
        raise UKPlanningSchemaError("Find a Tender UK3 release is missing tender planning data")
    _assert_procurement_act_notice(tender)
    if not _is_construction(tender):
        return None

    title = _text(tender.get("title"))
    if not title:
        raise UKPlanningSchemaError("Find a Tender UK3 construction plan is missing title")

    publication = _dt(release.get("date"))
    if publication is None:
        raise UKPlanningSchemaError("Find a Tender UK3 construction plan is missing publication date")

    communication = _dict(tender.get("communication"))
    future_notice = _dt(communication.get("futureNoticeDate"))
    buyer = _dict(release.get("buyer"))
    value = _dict(tender.get("value"))
    cpvs = _cpv_entries(tender.get("items"))
    contract_periods = [
        _dict(lot.get("contractPeriod"))
        for lot in _list(tender.get("lots"))
        if isinstance(lot, dict) and isinstance(lot.get("contractPeriod"), dict)
    ]

    return {
        "source": SOURCE,
        "signal_type": "PROCUREMENT_PLAN",
        "external_id": f"{ocid}:notice:{UK3_NOTICE_TYPE}",
        "source_reference": _text(release.get("id")),
        "notice_identifier": _text(release.get("id")),
        "notice_type": UK3_NOTICE_TYPE,
        "ocid": ocid,
        "title": title,
        "description": _text(tender.get("description")),
        "buyer": _text(buyer.get("name")),
        "country": COUNTRY,
        "publication_date": publication.date().isoformat(),
        "published_at": publication.isoformat().replace("+00:00", "Z"),
        "source_updated_at": publication.isoformat().replace("+00:00", "Z"),
        "target_date": future_notice.date().isoformat() if future_notice else None,
        "deadline": None,
        "value": str(value.get("amount")) if value.get("amount") is not None else None,
        "currency": _text(value.get("currency")) or None,
        "taxonomy": "CPV" if cpvs else None,
        "category_code": cpvs[0]["id"] if cpvs else None,
        "cpv_codes": [row["id"] for row in cpvs],
        "cpv_classifications": cpvs,
        "url": _text(document.get("url")),
        "procurement_method": _text(tender.get("procurementMethodDetails") or tender.get("procurementMethod")) or None,
        "contract_type": _text(tender.get("mainProcurementCategory")) or None,
        "planned_tender_publication": future_notice.isoformat().replace("+00:00", "Z") if future_notice else None,
        "planned_contract_periods": contract_periods,
        "license": FTS_LICENSE,
        "attribution": FTS_ATTRIBUTION,
        "source_dataset": "Find a Tender OCDS output",
        "source_modified": True,
        "construction_relevant": True,
    }


def normalize_uk3_releases(releases):
    """Normalize a window and collapse edited UK3 versions by stable logical id.

    When multiple versions occur in the same source window, the most recent
    publisher timestamp wins. Equal timestamps with different normalized content
    fail closed rather than silently choosing one version.
    """
    latest = {}
    latest_dates = {}
    for release in releases or []:
        row = normalize_uk3_release(release)
        if row is None:
            continue
        key = row["external_id"]
        observed = _dt(release.get("date"))
        previous = latest.get(key)
        previous_date = latest_dates.get(key)
        if previous is None or observed > previous_date:
            latest[key] = row
            latest_dates[key] = observed
            continue
        if observed == previous_date and row != previous:
            raise UKPlanningSchemaError(f"conflicting UK3 versions share timestamp for {key}")
    return [latest[key] for key in sorted(latest)]
