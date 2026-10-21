import unittest
from datetime import datetime, timedelta, timezone

from founder_control_center.registry import get_company, ingest_factory_state


class InternalFactoryIngestTests(unittest.TestCase):
    def _base(self):
        return {
            "company_id": "obrasignal",
            "factory_name": "Direct Internal Factory",
            "active": "Direct active",
            "next_value": "Direct next",
            "wait": "NONE",
            "source": "ci:direct-factory-ingest",
            "freshness_seconds": 900,
            "material_delta": "Direct canonical delta",
        }

    def test_internal_ingest_rejects_malformed_company_id_before_sqlite(self):
        for company_id in (["obrasignal"], {"id": "obrasignal"}, 42, "x" * 121):
            with self.assertRaisesRegex(ValueError, "company_id must be a non-empty string"):
                ingest_factory_state(**dict(self._base(), company_id=company_id))

    def test_internal_ingest_rejects_lossy_text_instead_of_truncating(self):
        cases = {
            "factory_name": ("x" * 161, "factory_name must be at most 160"),
            "active": ("x" * 1001, "active must be at most 1000"),
            "next_value": ("x" * 1001, "next must be at most 1000"),
            "wait": ("x" * 1001, "wait must be at most 1000"),
        }
        for field, (value, message) in cases.items():
            with self.assertRaisesRegex(ValueError, message):
                ingest_factory_state(**dict(self._base(), **{field: value}))

    def test_internal_ingest_rejects_invalid_material_delta_shape(self):
        for value in (123, True, ["delta"], {"delta": "value"}):
            with self.assertRaisesRegex(ValueError, "material_delta must be a string or null"):
                ingest_factory_state(**dict(self._base(), material_delta=value))
        with self.assertRaisesRegex(ValueError, "material_delta must be at most 2000"):
            ingest_factory_state(**dict(self._base(), material_delta="x" * 2001))

    def test_internal_ingest_does_not_promote_falsy_observed_at_to_now(self):
        for value in ("", False, 0):
            with self.assertRaisesRegex(ValueError, "observed_at must be ISO-8601"):
                ingest_factory_state(**dict(self._base(), observed_at=value))

    def test_identical_same_time_replay_is_idempotent_but_conflict_is_rejected(self):
        observed_at = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
        base = dict(self._base(), factory_name="Direct Same-Time Factory", observed_at=observed_at)
        first = ingest_factory_state(**base)
        first_factory = next(item for item in first.factories if item.name == "Direct Same-Time Factory")
        self.assertEqual(first_factory.active, "Direct active")

        replay = ingest_factory_state(**base)
        replay_factory = next(item for item in replay.factories if item.name == "Direct Same-Time Factory")
        self.assertEqual(replay_factory.active, "Direct active")

        with self.assertRaisesRegex(ValueError, "conflicting Factory state evidence at identical observed_at"):
            ingest_factory_state(**dict(base, active="Conflicting active"))
        persisted = next(item for item in get_company("obrasignal").factories if item.name == "Direct Same-Time Factory")
        self.assertEqual(persisted.active, "Direct active")


if __name__ == "__main__":
    unittest.main()
