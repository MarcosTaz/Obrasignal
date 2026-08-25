"""Reusable OCDS ReleasePackage hydration + multi-signal normalization support.

Some official OCDS publishers expose search/discovery rows and hydrate each OCID
through a ReleasePackage containing multiple releases. The base page connector
is intentionally conservative and historically normalized one record into one
signal. This extension preserves the complete release history for one OCID and
allows a source normalizer to emit several canonical signals from the same
hydration without duplicating network requests.

It is transport/family infrastructure, not a regional runtime.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from urllib.parse import quote

from ocds_adapter import OCDSAPIConnector, OCDSWindowCursor, _records_from_payload


def _text(value):
    return "" if value is None else str(value).strip()


def _unwrap_mapping(payload):
    value = payload
    if isinstance(value, dict) and isinstance(value.get("payload"), dict):
        value = value["payload"]
        if isinstance(value.get("content"), dict):
            value = value["content"]
    return value


def merge_nonempty_mapping(base, patch):
    """Recursively preserve prior fields omitted by a later partial OCDS patch.

    OCDS ReleasePackages may publish partial updates. Empty/missing values in a
    later release must not erase previously observed normalized context. Mapping
    children are merged recursively; non-empty scalar/list values replace the
    previous value. This is deliberately narrower than a full OCDS merge engine
    and is suitable for source normalizers that only read a bounded set of fields.
    """
    if not isinstance(base, Mapping):
        base = {}
    if not isinstance(patch, Mapping):
        return deepcopy(dict(base))
    merged = deepcopy(dict(base))
    for key, value in patch.items():
        if value in (None, "", [], {}):
            continue
        previous = merged.get(key)
        if isinstance(previous, Mapping) and isinstance(value, Mapping):
            merged[key] = merge_nonempty_mapping(previous, value)
        else:
            merged[key] = deepcopy(value)
    return merged


class OCDSReleasePackageConnector(OCDSAPIConnector):
    """Preserve all releases for an OCID and support one-to-many signal output."""

    def _hydrate_candidate(self, candidate):
        if not self.config.hydrate_records:
            return candidate
        template = str(self.config.record_url_template or "").strip()
        if not template:
            raise RuntimeError(
                f"{self.config.source} hydration enabled without record_url_template"
            )
        ocid = _text(candidate.get("ocid")) if isinstance(candidate, dict) else ""
        if not ocid:
            raise RuntimeError(
                f"{self.config.source} search candidate is missing ocid required for hydration"
            )

        url = template.format(ocid=quote(ocid, safe=""))
        response = self.session.get(
            url,
            params={},
            headers=self._headers(),
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        raw = response.json()
        payload = _unwrap_mapping(raw)

        # Preserve ReleasePackage history instead of collapsing it to the first
        # matching release. This is required for lifecycle state reconstruction.
        if isinstance(payload, dict) and isinstance(payload.get("releases"), list):
            releases = [
                release
                for release in payload["releases"]
                if isinstance(release, dict) and _text(release.get("ocid")) == ocid
            ]
            if not releases:
                raise RuntimeError(
                    f"{self.config.source} hydration ReleasePackage did not contain requested OCID {ocid}"
                )
            return {
                "ocid": ocid,
                "releases": releases,
                "uri": _text(payload.get("uri")),
                "_package_uri": _text(payload.get("uri")),
                "_package_version": payload.get("version"),
                "_package_published_date": payload.get("publishedDate"),
                "_package_license": payload.get("license"),
                "_package_publication_policy": payload.get("publicationPolicy"),
            }

        # Retain compatibility with record-like hydration shapes without issuing
        # a second HTTP request.
        records = _records_from_payload(raw)
        if not records:
            raise RuntimeError(
                f"{self.config.source} hydration returned no OCDS record for {ocid}"
            )
        for record in records:
            if _text(record.get("ocid")) == ocid:
                return record
        if len(records) == 1:
            return records[0]
        raise RuntimeError(
            f"{self.config.source} hydration response did not contain requested OCID {ocid}"
        )

    @staticmethod
    def _normalized_many(value):
        if value is None:
            return ()
        if isinstance(value, Mapping):
            return (value,)
        if isinstance(value, (list, tuple)):
            rows = []
            for item in value:
                if not isinstance(item, Mapping):
                    raise RuntimeError("OCDS multi-signal normalizer returned a non-mapping item")
                rows.append(item)
            return tuple(rows)
        raise RuntimeError("OCDS multi-signal normalizer must return mapping/list/tuple/None")

    def fetch_incremental_many(self, normalizer, *, watermark=None, now=None):
        """Fetch once per record and flatten canonical signals returned by normalizer."""
        rows = []
        cursor = None
        for start, end in self._windows(watermark, now):
            batch = self._fetch_window(start, end)
            for record in batch:
                for item in self._normalized_many(normalizer(record)):
                    if not item.get("external_id"):
                        raise RuntimeError(
                            f"{self.config.source} multi-signal normalizer returned item without external_id"
                        )
                    rows.append(dict(item))
            cursor = OCDSWindowCursor(end.isoformat()).encode()
        return rows, cursor
