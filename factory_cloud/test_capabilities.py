import unittest

from factory_cloud.capabilities import (
    Capability,
    CapabilityContractError,
    HIGH_RISK_CAPABILITIES,
    SAFE_REPOSITORY_CAPABILITIES,
    parse_capabilities,
    require_capabilities,
)


class CapabilityContractTests(unittest.TestCase):
    def test_safe_repository_capabilities_are_explicit_and_high_risk_disjoint(self):
        self.assertIn(Capability.READ_REPOSITORY, SAFE_REPOSITORY_CAPABILITIES)
        self.assertIn(Capability.WRITE_FILES, SAFE_REPOSITORY_CAPABILITIES)
        self.assertIn(Capability.MERGE_MAIN, HIGH_RISK_CAPABILITIES)
        self.assertIn(Capability.DEPLOY_PRODUCTION, HIGH_RISK_CAPABILITIES)
        self.assertTrue(SAFE_REPOSITORY_CAPABILITIES.isdisjoint(HIGH_RISK_CAPABILITIES))

    def test_high_risk_capability_is_rejected_without_separate_authority(self):
        with self.assertRaises(CapabilityContractError):
            parse_capabilities(["READ_REPOSITORY", "MERGE_MAIN"])
        with self.assertRaises(CapabilityContractError):
            parse_capabilities(["DEPLOY_PRODUCTION"])
        with self.assertRaises(CapabilityContractError):
            parse_capabilities(["ACCESS_CUSTOMER_DATA"])

    def test_unknown_or_implicit_capabilities_fail_closed(self):
        with self.assertRaises(CapabilityContractError):
            parse_capabilities(None)
        with self.assertRaises(CapabilityContractError):
            parse_capabilities(["UNLIMITED_REPOSITORY_AUTHORITY"])

    def test_required_capability_must_be_declared(self):
        declared = ["READ_REPOSITORY", "RUN_TESTS"]
        require_capabilities(declared, ["READ_REPOSITORY"])
        with self.assertRaises(CapabilityContractError):
            require_capabilities(declared, ["WRITE_FILES"])


if __name__ == "__main__":
    unittest.main()
