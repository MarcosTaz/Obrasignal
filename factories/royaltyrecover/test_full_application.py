import unittest
from decimal import Decimal

from application import create_full_app
from contract_store import ContractStore
from finding_store import FindingStore
from persisted_scan import run_persisted_scan
from repository import RoyaltyRepository
from royalty_engine import PeriodInput


class FullApplicationTests(unittest.TestCase):
    def setUp(self):
        self.repo = RoyaltyRepository.memory()
        keys = {"keys": [
            {"key_id": "a", "organization_id": "ORG-A", "secret": "analyst", "role": "ANALYST"},
            {"key_id": "r", "organization_id": "ORG-A", "secret": "reviewer", "role": "REVIEWER"},
            {"key_id": "b", "organization_id": "ORG-B", "secret": "other", "role": "ANALYST"},
        ]}
        self.app = create_full_app(api_keys=keys, repository=self.repo)
        self.app.testing = True
        self.client = self.app.test_client()
        self.a = {"X-RoyaltyRecover-API-Key": "analyst"}
        self.r = {"X-RoyaltyRecover-API-Key": "reviewer"}
        self.b = {"X-RoyaltyRecover-API-Key": "other"}
        self.repo.ensure_organization("ORG-A", "Alpha", "system")
        self.repo.ensure_organization("ORG-B", "Beta", "system")

    def tearDown(self):
        self.repo.close()

    def _candidate(self):
        licensor = self.repo.create_licensor("ORG-A", "University", "system")
        licensee = self.repo.create_licensee("ORG-A", "Tenant A Licensee", "system")
        agreement = self.repo.create_agreement("ORG-A", licensor["id"], licensee["id"], "Tenant A Patent Licence", "system")
        version = self.repo.add_agreement_version("ORG-A", agreement["id"], "v1", b"agreement", "system")
        contract_ev = self.repo.add_evidence("ORG-A", "AGREEMENT", b"5% net sales", "system")
        statement_ev = self.repo.add_evidence("ORG-A", "ROYALTY_STATEMENT", b"statement", "system")
        contracts = ContractStore(self.repo)
        clause = contracts.add_clause("ORG-A", version["id"], "4.2", "ROYALTY_RATE", "analyst", evidence_id=contract_ev["id"])
        contracts.set_clause_review_status("ORG-A", clause["id"], "REVIEWED", "reviewer", "checked")
        rule = contracts.add_royalty_rule("ORG-A", version["id"], clause["id"], "PERCENTAGE_NET_SALES", "EUR", "analyst", rate=Decimal("0.05"))
        contracts.set_rule_review_status("ORG-A", rule["id"], "REVIEWED", "reviewer", "checked")
        result = run_persisted_scan(
            self.repo, "ORG-A", agreement["id"], version["id"], rule["id"], "2026-01-01", "2026-03-31",
            PeriodInput(gross_sales=Decimal("120000"), permitted_deductions=Decimal("10000"), reported_royalty=Decimal("4500"), paid_royalty=Decimal("4500")),
            [statement_ev["id"]], "analyst",
        )
        return result.finding

    def test_operator_dashboard_requires_authentication(self):
        self.assertEqual(self.client.get("/app").status_code, 401)

    def test_operator_dashboard_is_tenant_scoped_and_non_claiming(self):
        self._candidate()
        page_a = self.client.get("/app", headers=self.a)
        page_b = self.client.get("/app", headers=self.b)
        self.assertEqual(page_a.status_code, 200)
        self.assertIn(b"Tenant A Licensee", page_a.data)
        self.assertIn(b"Claim-ready", page_a.data)
        self.assertIn(b">0</div>", page_a.data)
        self.assertNotIn(b"Tenant A Licensee", page_b.data)
        self.assertNotIn(b"Tenant A Patent Licence", page_b.data)

    def test_formal_audit_packet_endpoint_requires_reviewer_route(self):
        finding = self._candidate()
        blocked = self.client.get(f"/api/v1/findings/{finding['id']}/formal-audit-packet", headers=self.a)
        self.assertEqual(blocked.status_code, 400)
        routed = self.client.post(f"/api/v1/findings/{finding['id']}/review", json={
            "decision": "ROUTE_TO_FORMAL_AUDIT", "rationale": "books-and-records audit required"
        }, headers=self.r)
        self.assertEqual(routed.status_code, 201)
        packet = self.client.get(f"/api/v1/findings/{finding['id']}/formal-audit-packet", headers=self.a)
        self.assertEqual(packet.status_code, 200)
        data = packet.get_json()
        self.assertEqual(data["analytical_candidate_amount"], "1000.00")
        self.assertFalse(data["auditor_engaged"])
        self.assertFalse(data["claim_ready"])

    def test_other_tenant_cannot_read_formal_audit_packet(self):
        finding = self._candidate()
        FindingStore(self.repo).add_review("ORG-A", finding["id"], "reviewer", "REVIEWER", "ROUTE_TO_FORMAL_AUDIT", "route")
        self.assertEqual(self.client.get(f"/api/v1/findings/{finding['id']}/formal-audit-packet", headers=self.b).status_code, 404)


if __name__ == "__main__":
    unittest.main()
