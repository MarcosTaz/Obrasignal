"""Lifecycle-enriched Find a Tender connector using the existing UK transport.

No second runtime or source identity is introduced. The existing release-window
transport still owns pagination/cursor behavior and the existing record hydration
still owns current TENDER actionability. This subclass only preserves source-native
UK3 planning notices as canonical PROCUREMENT_PLAN Signals in the same atomic window.
"""
from uk_find_tender import UKFindTenderConnector
from uk_find_tender_planning import normalize_uk3_releases


class UKFindTenderLifecycleConnector(UKFindTenderConnector):
    def _process_release_window(self, releases, *, start, end, now=None):
        plans = normalize_uk3_releases(releases)
        tenders = super()._process_release_window(releases, start=start, end=end, now=now)
        return [*plans, *tenders]


def build_uk_lifecycle_connector(*, session=None, max_hydrations_per_window=250):
    return UKFindTenderLifecycleConnector(
        session=session,
        max_hydrations_per_window=max_hydrations_per_window,
    )


def fetch_uk_lifecycle_signals(*, watermark=None, now=None, connector=None):
    client = connector or build_uk_lifecycle_connector()
    return client.fetch_incremental(watermark=watermark, now=now)
