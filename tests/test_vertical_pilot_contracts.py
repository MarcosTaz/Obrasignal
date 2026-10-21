from pathlib import Path

from factory_cloud.pilot_contract import load_pilot_contract


def test_aviation_and_contractcredit_pilot_contracts_are_complete_and_fail_closed():
    aviation = load_pilot_contract(Path("vertical_apps/aviation_recovery/pilot.json"))
    credit = load_pilot_contract(Path("vertical_apps/contractcredit/pilot.json"))
    assert aviation["vertical"] == "aviation-lease-entitlement-recovery"
    assert credit["vertical"] == "contractcredit"
    assert aviation["production_authority"] is False
    assert credit["production_authority"] is False
    assert "outcome_record" in aviation["outputs"]
    assert "outcome_record" in credit["outputs"]
    assert aviation["pricing"]["status"] == "HYPOTHESIS"
    assert credit["pricing"]["status"] == "HYPOTHESIS"
    assert aviation["pilot_exit_criteria"][-1] == "pricing_validated_or_revised"
    assert credit["pilot_exit_criteria"][-1] == "pricing_validated_or_revised"
