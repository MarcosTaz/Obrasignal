from pathlib import Path

from master_execution_queue import MASTER_EXECUTION_QUEUE


def _item(item_id):
    return next(item for item in MASTER_EXECUTION_QUEUE if item.id == item_id)


def test_transaction_monetization_is_gated_behind_value_and_transaction_pilots():
    item = _item("Q237_TRANSACTION_MONETIZATION_ARCHITECTURE")
    assert item.state == "GATED"
    assert item.target_stage == "RESEARCH"
    assert set(item.dependencies) == {
        "Q218_TRADE_LOOP_PILOT",
        "Q235_MICROWORKS_ACTION_PILOT",
        "Q230_VALUE_CREATED",
    }


def test_monetization_constitution_forbids_pay_to_rank_and_preserves_independence():
    text = Path("ANCILLARY_REVENUE_TRANSACTION_MONETIZATION.md").read_text()
    assert "NO PAY-TO-RANK" in text
    assert "SaaS = base revenue" in text
    assert "Transaction/economic facts and monetization facts are separate concerns" in text
    assert "Commission` must never be a hidden input" in text
    assert "Never sell" in text


def test_future_transaction_contract_names_are_preserved_without_implying_implementation():
    text = Path("ANCILLARY_REVENUE_TRANSACTION_MONETIZATION.md").read_text()
    for name in (
        "Quote",
        "Supplier",
        "Transaction",
        "Referral",
        "Partner",
        "Commission",
        "FinancingRoute",
        "InsuranceRoute",
        "Booking",
        "Conversion",
    ):
        assert f"`{name}`" in text
    assert "This is not permission to create these tables/services now" in text
