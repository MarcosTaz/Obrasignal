import threading
import unittest

from founder_control_center.business_feed import ingest_business_metric
from founder_control_center.models import CompanyManifest
from founder_control_center.registry import get_company, ingest_factory_state, save_company


class AtomicMutationTests(unittest.TestCase):
    def test_concurrent_factory_and_metric_updates_do_not_lose_each_other(self):
        company_id = "atomic-feed-company"
        save_company(CompanyManifest(
            id=company_id,
            name="Atomic Feed Company",
            mission="Prove concurrent canonical feeds do not lose updates.",
        ))
        barrier = threading.Barrier(3)
        errors = []

        def factory_worker():
            try:
                barrier.wait()
                ingest_factory_state(
                    company_id=company_id,
                    factory_name="Atomic Factory",
                    active="Factory write",
                    next_value="Metric write",
                    wait="NONE",
                    source="ci:atomic-factory",
                    freshness_seconds=900,
                )
            except Exception as exc:  # pragma: no cover - assertion reports exact exception
                errors.append(exc)

        def metric_worker():
            try:
                barrier.wait()
                ingest_business_metric(
                    company_id=company_id,
                    metric_key="revenue",
                    value=321.5,
                    source="ci:atomic-metric",
                    freshness_seconds=900,
                    state="GREEN",
                )
            except Exception as exc:  # pragma: no cover - assertion reports exact exception
                errors.append(exc)

        threads = [threading.Thread(target=factory_worker), threading.Thread(target=metric_worker)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors, errors)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        loaded = get_company(company_id)
        self.assertEqual(loaded.revenue.value, 321.5)
        self.assertEqual(loaded.revenue.evidence.source, "ci:atomic-metric")
        factory = next(item for item in loaded.factories if item.name == "Atomic Factory")
        self.assertEqual(factory.active, "Factory write")
        self.assertEqual(factory.evidence.source, "ci:atomic-factory")


if __name__ == "__main__":
    unittest.main()
