from austria_kerndaten_incremental import (
    AustriaKerndatenIncrementalConnector,
    AustriaKerndatenIncrementalCursor,
)


class DummySession:
    def __init__(self):
        self.headers = {}


class DiscoveryConnector(AustriaKerndatenIncrementalConnector):
    def __init__(self):
        super().__init__(session=DummySession())

    def _catalog_dataset_ids(self):
        return ["current"]

    def _dataset_urls(self, dataset_id):
        assert dataset_id == "current"
        return ["https://current.example/kdq.xml"]


def test_successful_catalogue_snapshot_does_not_keep_retired_kdq_from_cursor():
    cursor = AustriaKerndatenIncrementalCursor(
        observed_through="2026-08-23T12:00:00Z",
        datasets={"retired": {"urls": ["https://retired.example/kdq.xml"]}},
        kdq_observed={"https://retired.example/kdq.xml": "2026-08-23T12:00:00Z"},
        tracked={},
        catchup={},
    )
    discovered = DiscoveryConnector()._discover(cursor)
    assert discovered == {"current": {"urls": ["https://current.example/kdq.xml"]}}
