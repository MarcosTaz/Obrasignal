import unittest

from factory_cloud.control_plane import RegistryError, activation_plan, build_queue, load_registry, validate_registry


class FactoryCloudControlPlaneTests(unittest.TestCase):
    def test_registry_loads_and_is_application_only(self):
        registry = load_registry()
        self.assertEqual(registry["registry_scope"], "application_development_only")
        self.assertTrue(all(app["kind"] == "application" for app in registry["applications"]))

    def test_queue_is_priority_ordered(self):
        queue = build_queue(load_registry())
        self.assertGreaterEqual(len(queue), 1)
        self.assertEqual(queue, sorted(queue, key=lambda item: (-item.priority, item.app_id)))

    def test_activation_requires_omega(self):
        registry = load_registry()
        with self.assertRaises(RegistryError):
            activation_plan("A", registry)

    def test_plan_preserves_safety_boundaries(self):
        plan = activation_plan("Ω", load_registry())
        self.assertFalse(plan["safety"]["automatic_merge"])
        self.assertFalse(plan["safety"]["automatic_deploy"])
        self.assertFalse(plan["safety"]["production_mutation"])
        self.assertFalse(plan["safety"]["cross_app_secret_or_data_authority"])

    def test_research_factory_is_rejected(self):
        registry = load_registry()
        bad = dict(registry)
        bad["applications"] = list(registry["applications"]) + [
            {
                "app_id": "research-only",
                "name": "Research Factory",
                "kind": "research",
                "activation": {"enabled": True, "mode": "repository_safe_execution", "priority": 1},
            }
        ]
        with self.assertRaises(RegistryError):
            validate_registry(bad)


if __name__ == "__main__":
    unittest.main()
