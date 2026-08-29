import copy
import unittest

from factory_cloud.control_plane import RegistryError, activation_plan, build_queue, load_registry, validate_registry


class FactoryCloudControlPlaneTests(unittest.TestCase):
    def test_registry_loads_and_is_application_only(self):
        registry = load_registry()
        self.assertEqual(registry["registry_scope"], "application_development_only")
        self.assertEqual(registry["activation_code"], "D")
        self.assertTrue(all(app["kind"] == "application" for app in registry["applications"]))

    def test_queue_is_priority_ordered(self):
        queue = build_queue(load_registry())
        self.assertGreaterEqual(len(queue), 1)
        self.assertEqual(queue, sorted(queue, key=lambda item: (-item.priority, item.app_id)))

    def test_activation_requires_d(self):
        registry = load_registry()
        for wrong_code in ("A", "X", "Ω"):
            with self.assertRaises(RegistryError):
                activation_plan(wrong_code, registry)
        self.assertEqual(activation_plan("D", registry)["activation_code"], "D")

    def test_plan_preserves_safety_boundaries_and_surfaces_capabilities(self):
        plan = activation_plan("D", load_registry())
        self.assertFalse(plan["safety"]["automatic_merge"])
        self.assertFalse(plan["safety"]["automatic_deploy"])
        self.assertFalse(plan["safety"]["production_mutation"])
        self.assertFalse(plan["safety"]["cross_app_secret_or_data_authority"])
        obra = next(item for item in plan["queue"] if item["app_id"] == "obrasignal")
        self.assertEqual(set(obra["adapter_capabilities"]), {"READ_REPOSITORY", "RUN_TESTS", "UPDATE_BATON"})

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

    def test_verified_execution_source_must_stay_on_canonical_repository(self):
        registry = load_registry()
        obra = next(app for app in registry["applications"] if app["app_id"] == "obrasignal")
        self.assertEqual(obra["source_truth"]["canonical_branch"], "main")
        self.assertNotEqual(obra["execution_source"]["branch"], "main")
        self.assertNotEqual(obra["execution_source"]["head"], obra["source_truth"]["canonical_head"])
        self.assertEqual(obra["execution_source"]["repository"], obra["source_truth"]["repository"])
        self.assertTrue(obra["execution_source"]["verified"])

        unverified = copy.deepcopy(registry)
        next(app for app in unverified["applications"] if app["app_id"] == "obrasignal")["execution_source"]["verified"] = False
        with self.assertRaises(RegistryError):
            validate_registry(unverified)

        other_repo = copy.deepcopy(registry)
        next(app for app in other_repo["applications"] if app["app_id"] == "obrasignal")["execution_source"]["repository"] = "MarcosTaz/Other"
        with self.assertRaises(RegistryError):
            validate_registry(other_repo)

        bad_sha = copy.deepcopy(registry)
        next(app for app in bad_sha["applications"] if app["app_id"] == "obrasignal")["execution_source"]["head"] = "not-a-sha"
        with self.assertRaises(RegistryError):
            validate_registry(bad_sha)

    def test_high_risk_or_implicit_capability_escalation_is_rejected(self):
        registry = copy.deepcopy(load_registry())
        obra = next(app for app in registry["applications"] if app["app_id"] == "obrasignal")
        obra["execution_adapter"]["capabilities"].append("MERGE_MAIN")
        with self.assertRaises(RegistryError):
            validate_registry(registry)

        missing = copy.deepcopy(load_registry())
        obra = next(app for app in missing["applications"] if app["app_id"] == "obrasignal")
        obra["execution_adapter"].pop("capabilities")
        with self.assertRaises(RegistryError):
            validate_registry(missing)

    def test_task_capability_contract_must_match_allowlist_and_declared_authority(self):
        registry = copy.deepcopy(load_registry())
        obra = next(app for app in registry["applications"] if app["app_id"] == "obrasignal")
        task = obra["execution_adapter"]["allowlisted_tasks"][0]
        obra["task_capabilities"][task].append("WRITE_FILES")
        with self.assertRaises(RegistryError):
            validate_registry(registry)

        missing_task = copy.deepcopy(load_registry())
        obra = next(app for app in missing_task["applications"] if app["app_id"] == "obrasignal")
        obra["task_capabilities"].pop(obra["execution_adapter"]["allowlisted_tasks"][0])
        with self.assertRaises(RegistryError):
            validate_registry(missing_task)

    def test_read_only_app_cannot_gain_execution_source_or_capabilities(self):
        registry = copy.deepcopy(load_registry())
        k3 = next(app for app in registry["applications"] if app["app_id"] == "k3-fatality")
        k3["execution_source"] = {
            "provider": "github",
            "repository": "MarcosTaz/k3-fatality",
            "branch": "main",
            "head": "a" * 40,
            "verified": True,
        }
        with self.assertRaises(RegistryError):
            validate_registry(registry)

        registry = copy.deepcopy(load_registry())
        k3 = next(app for app in registry["applications"] if app["app_id"] == "k3-fatality")
        k3["execution_adapter"] = {
            "configured": True,
            "allowlisted_tasks": ["unsafe"],
            "capabilities": ["READ_REPOSITORY"],
            "repository_mutation_capability": False,
        }
        k3["task_capabilities"] = {"unsafe": ["READ_REPOSITORY"]}
        with self.assertRaises(RegistryError):
            validate_registry(registry)


if __name__ == "__main__":
    unittest.main()
