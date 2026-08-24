"""Single canonical execution queue for ObraSignal.

Every significant market, architecture, product, research or intelligence item must
enter this ordered queue.  Supporting roadmaps may describe a domain but may not
create an independent execution order.

The queue is intentionally conservative: only one item is ACTIVE at a time and
future capabilities are gated by explicit dependencies and maturity stages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExecutionState = Literal["DONE", "ACTIVE", "QUEUED", "GATED", "FUTURE"]
MaturityStage = Literal["RESEARCH", "PROTOTYPE", "PILOT", "PRODUCTION"]


@dataclass(frozen=True)
class ExecutionItem:
    id: str
    title: str
    domain: str
    state: ExecutionState
    target_stage: MaturityStage
    dependencies: tuple[str, ...] = ()
    reason: str = ""


CANONICAL_QUEUE_NAME = "OBRASIGNAL_MASTER_EXECUTION_QUEUE"
CURRENT_ITEM_ID = "Q010_BR_PNCP_DISCOVERY"

MASTER_EXECUTION_QUEUE = (
    ExecutionItem(
        "Q000_SCOPE_REBASE",
        "International market-scope rebase",
        "STRATEGY",
        "DONE",
        "PRODUCTION",
        reason="Canonical active coverage reduced to 45 markets and country-specific development gated to BUILD.",
    ),
    ExecutionItem(
        "Q010_BR_PNCP_DISCOVERY",
        "Brazil PNCP national PCA discovery contract",
        "SIGNAL",
        "ACTIVE",
        "RESEARCH",
        ("Q000_SCOPE_REBASE",),
        "Brazil is the first unfinished BUILD market; publisher-native construction PCA categories are proven, but safe national discovery is not yet production-proven.",
    ),
    ExecutionItem(
        "Q020_SIGNAL_CONTRACT_V1",
        "Generic provenance-first Signal contract and persistence",
        "SIGNAL",
        "QUEUED",
        "PRODUCTION",
        ("Q000_SCOPE_REBASE",),
        "PROCUREMENT_PLAN and future FORECAST/ASSET/OBLIGATION signals must not be silently persisted as legacy tenders.",
    ),
    ExecutionItem(
        "Q030_BR_PNCP_PCA",
        "Brazil PNCP construction procurement-plan connector",
        "SIGNAL",
        "GATED",
        "PRODUCTION",
        ("Q010_BR_PNCP_DISCOVERY", "Q020_SIGNAL_CONTRACT_V1"),
        "Promote only after national discovery, publisher-native categories, identity, pagination, freshness and fail-closed semantics are proven.",
    ),
    ExecutionItem(
        "Q040_CANADA_BUYS",
        "CanadaBuys federal construction connector",
        "SIGNAL",
        "QUEUED",
        "PRODUCTION",
        ("Q020_SIGNAL_CONTRACT_V1",),
        "High-ARPU BUILD market; federal-first avoids premature provincial fragmentation.",
    ),
    ExecutionItem(
        "Q050_US_SAM",
        "SAM.gov federal construction opportunities connector",
        "SIGNAL",
        "QUEUED",
        "PRODUCTION",
        ("Q020_SIGNAL_CONTRACT_V1",),
        "Highest absolute commercial upside; federal opportunities first, SLED later only if justified.",
    ),
    ExecutionItem(
        "Q060_CHILE_MERCADOPUBLICO",
        "Chile Mercado Público construction connector",
        "SIGNAL",
        "QUEUED",
        "PRODUCTION",
        ("Q020_SIGNAL_CONTRACT_V1",),
        "Strong official API and favourable value-to-effort ratio.",
    ),
    ExecutionItem(
        "Q070_SHARED_FAMILIES",
        "Harden TED/eForms and OCDS shared-coverage families",
        "SIGNAL",
        "QUEUED",
        "PRODUCTION",
        ("Q030_BR_PNCP_PCA", "Q040_CANADA_BUYS", "Q050_US_SAM", "Q060_CHILE_MERCADOPUBLICO"),
        "Maximise supported markets per maintained connector and eliminate country-specific duplication.",
    ),
    ExecutionItem(
        "Q080_EVIDENCE_GRAPH_V1",
        "Proof / Evidence Graph v1",
        "COMMAND",
        "QUEUED",
        "PRODUCTION",
        ("Q020_SIGNAL_CONTRACT_V1",),
        "All important recommendations need traceable WHY / SHOW ME / WHAT IF evidence before higher autonomy is safe.",
    ),
    ExecutionItem(
        "Q090_COMPANY_STATE_CONTRACT",
        "Company operational-state contract",
        "OFFICE",
        "QUEUED",
        "PROTOTYPE",
        ("Q080_EVIDENCE_GRAPH_V1",),
        "Define the minimal internal facts required for capacity and economics without building a generic ERP.",
    ),
    ExecutionItem(
        "Q100_OUTCOME_GRAPH_V1",
        "Outcome Graph and decision-result capture",
        "DNA",
        "QUEUED",
        "PROTOTYPE",
        ("Q080_EVIDENCE_GRAPH_V1", "Q090_COMPANY_STATE_CONTRACT"),
        "Win/loss/no-bid, predicted-vs-actual and decision outcomes are prerequisites for Contractor DNA and regret prevention.",
    ),
    ExecutionItem(
        "Q110_DYNAMIC_ELIGIBILITY_RESEARCH",
        "Dynamic Eligibility / Opportunity Unlock research",
        "COMMAND",
        "QUEUED",
        "RESEARCH",
        ("Q090_COMPANY_STATE_CONTRACT",),
        "Test whether workforce/equipment/qualification/capital blockers can be identified and legally/economically unlocked.",
    ),
    ExecutionItem(
        "Q120_OFFICE_SENSOR_RESEARCH",
        "OFFICE sensor architecture and integrate-vs-build audit",
        "OFFICE",
        "QUEUED",
        "RESEARCH",
        ("Q090_COMPANY_STATE_CONTRACT",),
        "Select only operational inputs that materially improve decisions; integrate generic software rather than rebuild it.",
    ),
    ExecutionItem(
        "Q130_CREW_CAPACITY_SENSOR",
        "Minimal crew/capacity sensor",
        "OFFICE",
        "GATED",
        "PROTOTYPE",
        ("Q120_OFFICE_SENSOR_RESEARCH",),
        "Prototype radically simple workforce availability, hours and current-work capture with proportional privacy.",
    ),
    ExecutionItem(
        "Q140_CONTRACTOR_DNA_V1",
        "Contractor DNA v1",
        "DNA",
        "GATED",
        "PROTOTYPE",
        ("Q100_OUTCOME_GRAPH_V1", "Q130_CREW_CAPACITY_SENSOR"),
        "Learn operational truth from predicted versus actual productivity, duration, margin and capacity behaviour.",
    ),
    ExecutionItem(
        "Q150_SHADOW_PORTFOLIO_RESEARCH",
        "SHADOW portfolio-optimisation research",
        "SHADOW",
        "GATED",
        "RESEARCH",
        ("Q090_COMPANY_STATE_CONTRACT", "Q140_CONTRACTOR_DNA_V1"),
        "Validate scenario inputs, constraints and decision usefulness before building a probabilistic contractor twin.",
    ),
    ExecutionItem(
        "Q160_SHADOW_PORTFOLIO_PROTOTYPE",
        "SHADOW portfolio optimiser prototype",
        "SHADOW",
        "GATED",
        "PROTOTYPE",
        ("Q150_SHADOW_PORTFOLIO_RESEARCH",),
        "Compare combinations of opportunities across cash, workforce, equipment, mobilisation, management capacity and risk.",
    ),
    ExecutionItem(
        "Q170_COMMAND_NEXT_BEST_ACTION",
        "COMMAND next-best-action engine v1",
        "COMMAND",
        "GATED",
        "PROTOTYPE",
        ("Q080_EVIDENCE_GRAPH_V1", "Q110_DYNAMIC_ELIGIBILITY_RESEARCH", "Q160_SHADOW_PORTFOLIO_PROTOTYPE"),
        "Move from ranked information to a small number of quantified, evidence-backed next decisions.",
    ),
    ExecutionItem(
        "Q180_ACTION_ARCHITECTURE",
        "ACTION execution architecture",
        "ACTION",
        "GATED",
        "RESEARCH",
        ("Q170_COMMAND_NEXT_BEST_ACTION",),
        "Define safe authorisation, consent, audit and rollback boundaries before automating RFQs, outreach or financing workflows.",
    ),
    ExecutionItem(
        "Q190_FUTURE_DEMAND_ASSET_CLOCK",
        "Future Demand Engine / Asset Clock research",
        "SIGNAL",
        "GATED",
        "RESEARCH",
        ("Q020_SIGNAL_CONTRACT_V1", "Q080_EVIDENCE_GRAPH_V1"),
        "Test whether asset lifecycle and public-data signals predict physical work early enough to create commercial action.",
    ),
    ExecutionItem(
        "Q200_FORCED_DEMAND",
        "Forced Demand / Obligation-to-Opportunity research",
        "SIGNAL",
        "GATED",
        "RESEARCH",
        ("Q020_SIGNAL_CONTRACT_V1", "Q080_EVIDENCE_GRAPH_V1"),
        "Validate rule-to-asset-to-work translation with legal traceability before any LAW → BILL OF WORKS product claim.",
    ),
    ExecutionItem(
        "Q210_SUPPLY_EDGE",
        "Bid-to-Supply Intelligence research",
        "ACTION",
        "GATED",
        "RESEARCH",
        ("Q090_COMPANY_STATE_CONTRACT", "Q180_ACTION_ARCHITECTURE"),
        "Determine whether specification/BoQ sourcing can produce measurable margin improvement with independent supplier ranking.",
    ),
    ExecutionItem(
        "Q220_WORK_PACKAGE_RELEASE",
        "Work Package Release Prediction research",
        "SIGNAL",
        "GATED",
        "RESEARCH",
        ("Q020_SIGNAL_CONTRACT_V1", "Q100_OUTCOME_GRAPH_V1"),
        "Test whether package timing, prime identity and subcontract release windows can be predicted accurately enough for outreach.",
    ),
    ExecutionItem(
        "Q230_VALUE_CREATED",
        "Measured and estimated Value Created framework",
        "COMMAND",
        "GATED",
        "PROTOTYPE",
        ("Q100_OUTCOME_GRAPH_V1", "Q170_COMMAND_NEXT_BEST_ACTION"),
        "Quantify legitimate product value without fabricating ROI and support regret-prevention learning.",
    ),
    ExecutionItem(
        "Q240_GROWTH_SIMULATOR",
        "Contractor Growth Simulator",
        "SHADOW",
        "GATED",
        "RESEARCH",
        ("Q160_SHADOW_PORTFOLIO_PROTOTYPE", "Q110_DYNAMIC_ELIGIBILITY_RESEARCH"),
        "Evaluate what the company should become only after constraints and portfolio economics are credible.",
    ),
    ExecutionItem(
        "Q250_RESCUE_MODE",
        "Rescue Mode / Rescue Signal research",
        "SIGNAL",
        "GATED",
        "RESEARCH",
        ("Q020_SIGNAL_CONTRACT_V1", "Q130_CREW_CAPACITY_SENSOR"),
        "Explore urgent post-award replacement/capacity demand only when supply and availability can be represented safely.",
    ),
    ExecutionItem(
        "Q260_BENCHMARK_NETWORK",
        "Privacy-preserving benchmark network",
        "DNA",
        "FUTURE",
        "RESEARCH",
        ("Q140_CONTRACTOR_DNA_V1", "Q230_VALUE_CREATED"),
        "Requires sufficient cohort size, anonymisation thresholds and competition/privacy safeguards.",
    ),
    ExecutionItem(
        "Q270_LIVE_CAPACITY_NETWORK",
        "Live Capacity Network",
        "ACTION",
        "FUTURE",
        "RESEARCH",
        ("Q130_CREW_CAPACITY_SENSOR", "Q180_ACTION_ARCHITECTURE", "Q260_BENCHMARK_NETWORK"),
        "Do not build a marketplace before verified capacity, trust and sufficient network density exist.",
    ),
    ExecutionItem(
        "Q280_CHAIN_REACTION",
        "Chain-Reaction Intelligence research",
        "SIGNAL",
        "FUTURE",
        "RESEARCH",
        ("Q190_FUTURE_DEMAND_ASSET_CLOCK",),
        "Second- and third-order demand prediction remains a hypothesis until precision and actionability are demonstrated.",
    ),
)


def queue_ids() -> tuple[str, ...]:
    return tuple(item.id for item in MASTER_EXECUTION_QUEUE)


def current_item() -> ExecutionItem:
    active = [item for item in MASTER_EXECUTION_QUEUE if item.state == "ACTIVE"]
    if len(active) != 1:
        raise RuntimeError(f"master queue must contain exactly one ACTIVE item, found {len(active)}")
    item = active[0]
    if item.id != CURRENT_ITEM_ID:
        raise RuntimeError("CURRENT_ITEM_ID does not match the ACTIVE queue item")
    return item


def next_executable_after_current() -> tuple[ExecutionItem, ...]:
    """Return ordered items whose dependencies are already DONE or the current item.

    This is intentionally advisory rather than an automatic state-mutator. Execution
    state changes are reviewed/committed alongside the work that satisfies a gate.
    """
    completed = {item.id for item in MASTER_EXECUTION_QUEUE if item.state == "DONE"}
    completed.add(CURRENT_ITEM_ID)
    return tuple(
        item
        for item in MASTER_EXECUTION_QUEUE
        if item.state in {"QUEUED", "GATED", "FUTURE"}
        and all(dep in completed for dep in item.dependencies)
    )
