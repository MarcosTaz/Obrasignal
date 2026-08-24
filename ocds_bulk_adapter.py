"""Reusable monthly OCDS bulk discovery with bounded record hydration.

Designed for official publishers that expose month-partitioned ZIP/JSON release
packages plus an OCID record endpoint. Bulk files discover changed OCIDs; record
hydration provides the publisher's current compiled state. The transport never
uses keyword search as a substitute for complete discovery.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import json
import zipfile

import requests


@dataclass(frozen=True)
class OCDSMonthlyBulkConfig:
    source: str
    country: str
    bulk_url_template: str
    record_url: str
    market: str = "GLOBAL"
    overlap_months: int = 1
    max_packages_per_file: int = 500000
    max_hydrations_per_sync: int = 500
    timeout: int = 90
    user_agent: str = "ObraSignal procurement connector/1.0"


@dataclass(frozen=True)
class OCDSMonthlyBulkCursor:
    observed_through: str
    periods: tuple[str, ...]

    def encode(self):
        return json.dumps(
            {"observed_through": self.observed_through, "periods": list(self.periods)},
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def decode(cls, value):
        if not value:
            return None
        try:
            payload = json.loads(str(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        observed = str(payload.get("observed_through") or "").strip()
        periods = payload.get("periods")
        if not observed or not isinstance(periods, list):
            return None
        return cls(observed, tuple(str(period) for period in periods if period))


def _month_start(value):
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)


def _shift_month(month, offset):
    index = month.year * 12 + (month.month - 1) + int(offset)
    return datetime(index // 12, index % 12 + 1, 1, tzinfo=timezone.utc)


def _periods(now, overlap_months):
    current = _month_start(now)
    count = max(0, int(overlap_months))
    return [_shift_month(current, -offset) for offset in range(count, -1, -1)]


def _release_from_package(package):
    if not isinstance(package, dict):
        return None
    releases = package.get("releases")
    if not isinstance(releases, list):
        return None
    candidates = [row for row in releases if isinstance(row, dict)]
    if not candidates:
        return None
    return max(candidates, key=lambda row: str(row.get("date") or ""))


def record_from_payload(payload, requested_ocid=None):
    """Normalize documented RecordPackage and observed ReleasePackage shapes."""
    if not isinstance(payload, dict):
        raise RuntimeError("OCDS record response is not an object")

    records = payload.get("records")
    if isinstance(records, list):
        candidates = [row for row in records if isinstance(row, dict)]
        if requested_ocid:
            for record in candidates:
                if str(record.get("ocid") or "") == str(requested_ocid):
                    return record
        if len(candidates) == 1:
            return candidates[0]
        raise RuntimeError("OCDS record package did not contain the requested OCID")

    releases = payload.get("releases")
    if isinstance(releases, list):
        candidates = [row for row in releases if isinstance(row, dict)]
        if not candidates:
            raise RuntimeError("OCDS release package contained no releases")
        ocids = {str(row.get("ocid") or "") for row in candidates if row.get("ocid")}
        if requested_ocid and ocids and str(requested_ocid) not in ocids:
            raise RuntimeError("OCDS release package did not contain the requested OCID")
        return {
            "ocid": str(requested_ocid or candidates[-1].get("ocid") or ""),
            "releases": candidates,
            "_package_uri": payload.get("uri"),
            "_package_license": payload.get("license"),
            "_package_publication_policy": payload.get("publicationPolicy"),
            "_package_published_date": payload.get("publishedDate"),
            "_package_version": payload.get("version"),
        }

    if payload.get("ocid") and (payload.get("compiledRelease") or payload.get("releases")):
        return payload
    raise RuntimeError("Unsupported OCDS record response shape")


class OCDSMonthlyBulkConnector:
    def __init__(self, config, *, candidate_selector, normalizer, session=None):
        self.config = config
        self.candidate_selector = candidate_selector
        self.normalizer = normalizer
        self.session = session or requests.Session()

    def _headers(self, accept):
        return {"Accept": accept, "User-Agent": self.config.user_agent}

    def _bulk_url(self, period):
        return self.config.bulk_url_template.format(year=period.year, month=f"{period.month:02d}")

    def _download_packages(self, period):
        response = self.session.get(
            self._bulk_url(period),
            headers=self._headers("application/zip, application/octet-stream"),
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        payload = response.content
        if not zipfile.is_zipfile(BytesIO(payload)):
            raise RuntimeError(f"{self.config.source} {period:%Y-%m} bulk response is not a ZIP archive")
        packages = []
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            json_names = [name for name in archive.namelist() if name.lower().endswith(".json")]
            if not json_names:
                raise RuntimeError(f"{self.config.source} {period:%Y-%m} bulk ZIP contains no JSON")
            for name in json_names:
                with archive.open(name) as handle:
                    root = json.load(handle)
                if isinstance(root, list):
                    packages.extend(row for row in root if isinstance(row, dict))
                elif isinstance(root, dict):
                    packages.append(root)
                else:
                    raise RuntimeError(f"{self.config.source} {period:%Y-%m} JSON has unsupported root shape")
                if len(packages) > int(self.config.max_packages_per_file):
                    raise RuntimeError(
                        f"{self.config.source} {period:%Y-%m} exceeds max_packages_per_file="
                        f"{self.config.max_packages_per_file}"
                    )
        return packages

    def _candidate_ocids(self, packages):
        ocids = []
        seen = set()
        for package in packages:
            release = _release_from_package(package)
            if not release or not self.candidate_selector(package, release):
                continue
            ocid = str(release.get("ocid") or "").strip()
            if not ocid or ocid in seen:
                continue
            seen.add(ocid)
            ocids.append(ocid)
        return ocids

    def _hydrate(self, ocid):
        response = self.session.get(
            self.config.record_url,
            params={"ocid": ocid},
            headers=self._headers("application/json"),
            timeout=min(int(self.config.timeout), 60),
        )
        response.raise_for_status()
        return record_from_payload(response.json(), requested_ocid=ocid)

    def fetch_incremental(self, *, watermark=None, now=None):
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        current = current.astimezone(timezone.utc)
        periods = _periods(current, self.config.overlap_months)

        packages = []
        for period in periods:
            packages.extend(self._download_packages(period))
        ocids = self._candidate_ocids(packages)
        if len(ocids) > int(self.config.max_hydrations_per_sync):
            raise RuntimeError(
                f"{self.config.source} requires {len(ocids)} record hydrations, above "
                f"max_hydrations_per_sync={self.config.max_hydrations_per_sync}; cursor not advanced"
            )

        observations = []
        for ocid in ocids:
            record = self._hydrate(ocid)
            item = self.normalizer(record, now=current)
            if item and item.get("external_id"):
                observations.append(item)

        cursor = OCDSMonthlyBulkCursor(
            observed_through=current.date().isoformat(),
            periods=tuple(period.strftime("%Y-%m") for period in periods),
        ).encode()
        return observations, cursor
