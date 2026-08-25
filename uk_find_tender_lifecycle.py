"""Lifecycle-enriched Find a Tender connector using the existing UK transport.

No second runtime or source identity is introduced. The existing release-window
transport still owns pagination/cursor behavior and current record hydration still
owns TENDER actionability. This subclass preserves source-native UK3 notices as
PROCUREMENT_PLAN and prevents planning-only OCIDs from being relabelled as TENDER
lifecycle records merely because OCDS stores planning data under ``tender`` fields.
"""
from uk_find_tender import UKFindTenderConnector
from uk_find_tender_planning import normalize_uk3_releases


_PLANNING_TAGS = frozenset({"planning", "planningUpdate"})


def _tags(release):
    if not isinstance(release, dict):
        return set()
    raw = release.get("tag")
    if not isinstance(raw, list):
        return set()
    return {str(value).strip() for value in raw if str(value).strip()}


def _releases_requiring_current_tender_hydration(releases):
    """Keep existing hydration except for OCIDs proven planning-only in this window.

    Missing/unknown tags deliberately retain the previous conservative behavior and
    are hydrated. An OCID is skipped only when every observed release for it has a
    publisher planning/planningUpdate tag. If any non-planning release exists for the
    OCID in the same window, all its releases are passed through so the parent keeps
    its existing once-per-OCID deduplication and current-state lifecycle handling.
    """
    releases = list(releases or [])
    by_ocid = {}
    for release in releases:
        if not isinstance(release, dict):
            # Parent owns fail-closed malformed-release behavior.
            return releases
        ocid = str(release.get("ocid") or "").strip()
        if not ocid:
            return releases
        by_ocid.setdefault(ocid, []).append(release)

    hydrate_ocids = set()
    for ocid, grouped in by_ocid.items():
        if any(not _tags(row) or not _tags(row).issubset(_PLANNING_TAGS) for row in grouped):
            hydrate_ocids.add(ocid)
    return [row for row in releases if str(row.get("ocid") or "").strip() in hydrate_ocids]


class UKFindTenderLifecycleConnector(UKFindTenderConnector):
    def _process_release_window(self, releases, *, start, end, now=None):
        plans = normalize_uk3_releases(releases)
        hydration_releases = _releases_requiring_current_tender_hydration(releases)
        tenders = super()._process_release_window(
            hydration_releases,
            start=start,
            end=end,
            now=now,
        )
        return [*plans, *tenders]


def build_uk_lifecycle_connector(*, session=None, max_hydrations_per_window=250):
    return UKFindTenderLifecycleConnector(
        session=session,
        max_hydrations_per_window=max_hydrations_per_window,
    )


def fetch_uk_lifecycle_signals(*, watermark=None, now=None, connector=None):
    client = connector or build_uk_lifecycle_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
