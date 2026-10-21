import os
import tempfile
import unittest

_tmp = tempfile.NamedTemporaryFile(prefix="fcc-core-", suffix=".db", delete=False)
_tmp.close()
os.environ["FCC_DB"] = _tmp.name

from founder_control_center.actions import execute
from founder_control_center.models import TruthState
from founder_control_center.ranking import highest_value_actions, rank_portfolio
from founder_control_center.registry import get_company, init_db, list_companies


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_registry_truth(self):
        companies = list_companies()
        self.assertGreaterEqual(len(companies), 8)
        self.assertEqual(get_company("obrasignal").revenue.state, TruthState.UNKNOWN)
        self.assertEqual(get_company("money-leakage-auditor").data_freshness, TruthState.UNKNOWN)

    def test_ranking_uncertainty(self):
        ranks = rank_portfolio(list_companies())
        self.assertTrue(all(0 <= r.uncertainty <= 1 for r in ranks))
        self.assertTrue(highest_value_actions(list_companies()))

    def test_action_boundaries(self):
        self.assertEqual(execute("delete_customer_data", "obrasignal", {})[1], 403)
        self.assertEqual(execute("prepare_deployment", "obrasignal", {})[1], 202)
        body, status = execute("update_factory_state", "founder-control-center", {"active":"Core validation"})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])


if __name__ == "__main__":
    unittest.main()
