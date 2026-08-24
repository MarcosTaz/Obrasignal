"""Single canonical execution queue for ObraSignal.

Every significant market, architecture, product, research or intelligence item
must enter this ordered queue. Supporting roadmaps may describe a domain but may
not create an independent execution order.

Exactly one item is ACTIVE. Dependencies determine readiness; queue order decides
which ready item executes next. This keeps the user out of plan coordination.
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


def _q(id, title, domain, state, stage, dependencies=(), reason=""):
    return ExecutionItem(id, title, domain, state, stage, tuple(dependencies), reason)


CANONICAL_QUEUE_NAME = "OBRASIGNAL_MASTER_EXECUTION_QUEUE"
CURRENT_ITEM_ID = "Q030_BR_PNCP_PCA"

MASTER_EXECUTION_QUEUE = (
    _q("Q000_SCOPE_REBASE", "International market-scope rebase", "STRATEGY", "DONE", "PRODUCTION",
       reason="Active coverage fixed at 45 markets; bespoke development is BUILD-only."),
    _q("Q010_BR_PNCP_DISCOVERY", "Brazil PNCP national PCA discovery contract", "SIGNAL", "DONE", "RESEARCH",
       ("Q000_SCOPE_REBASE",),
       "Publisher-native Works categories, public national discovery, pagination, identity, update timestamp and recent-first ordering were live-proven."),
    _q("Q020_SIGNAL_CONTRACT_V1", "Generic provenance-first Signal contract and persistence", "SIGNAL", "DONE", "PRODUCTION",
       ("Q000_SCOPE_REBASE",),
       "Signal persistence is durable and transactional; explicit non-TENDER records cannot masquerade as legacy tenders."),
    _q("Q030_BR_PNCP_PCA", "Brazil PNCP construction procurement-plan connector", "SIGNAL", "ACTIVE", "PRODUCTION",
       ("Q010_BR_PNCP_DISCOVERY", "Q020_SIGNAL_CONTRACT_V1"),
       "Implement bounded recent-first discovery, publisher-native Works categories, item hydration, identity, cursor/drift safety and opt-in runtime wiring."),
    _q("Q040_CANADA_BUYS", "CanadaBuys federal construction connector", "SIGNAL", "QUEUED", "PRODUCTION",
       ("Q020_SIGNAL_CONTRACT_V1",), "High-ARPU BUILD market; federal-first avoids premature provincial fragmentation."),
    _q("Q050_US_SAM", "SAM.gov federal construction opportunities connector", "SIGNAL", "QUEUED", "PRODUCTION",
       ("Q020_SIGNAL_CONTRACT_V1",), "Highest absolute commercial upside; federal opportunities first, SLED only if justified."),
    _q("Q060_CHILE_MERCADOPUBLICO", "Chile Mercado Público construction connector", "SIGNAL", "QUEUED", "PRODUCTION",
       ("Q020_SIGNAL_CONTRACT_V1",), "Strong official API and favourable value-to-effort ratio."),
    _q("Q070_SHARED_FAMILIES", "Harden TED/eForms and OCDS shared-coverage families", "SIGNAL", "QUEUED", "PRODUCTION",
       ("Q030_BR_PNCP_PCA", "Q040_CANADA_BUYS", "Q050_US_SAM", "Q060_CHILE_MERCADOPUBLICO"),
       "Maximise supported markets per maintained connector and remove country-specific duplication."),
    _q("Q080_EVIDENCE_GRAPH_V1", "Proof / Evidence Graph v1", "COMMAND", "QUEUED", "PRODUCTION",
       ("Q020_SIGNAL_CONTRACT_V1",), "Material recommendations need traceable WHY / SHOW ME / WHAT IF evidence before higher autonomy is safe."),
    _q("Q090_COMPANY_STATE_CONTRACT", "Company operational-state contract", "OFFICE", "QUEUED", "PROTOTYPE",
       ("Q080_EVIDENCE_GRAPH_V1",), "Define the minimum internal facts needed for capacity and economics without building a generic ERP."),
    _q("Q100_OUTCOME_GRAPH_V1", "Outcome Graph and decision-result capture", "DNA", "QUEUED", "PROTOTYPE",
       ("Q080_EVIDENCE_GRAPH_V1", "Q090_COMPANY_STATE_CONTRACT"),
       "Capture win/loss/no-bid and predicted-vs-actual outcomes for Contractor DNA, regret learning and later supplier truth."),
    _q("Q110_DYNAMIC_ELIGIBILITY_RESEARCH", "Dynamic Eligibility / Opportunity Unlock research", "COMMAND", "QUEUED", "RESEARCH",
       ("Q090_COMPANY_STATE_CONTRACT",), "Test whether resource, qualification, partner, capital and guarantee blockers can be legally/economically unlocked."),
    _q("Q120_OFFICE_SENSOR_RESEARCH", "OFFICE sensor architecture and integrate-vs-build audit", "OFFICE", "QUEUED", "RESEARCH",
       ("Q090_COMPANY_STATE_CONTRACT",), "Select only operational inputs that improve decisions; integrate generic software instead of rebuilding it."),
    _q("Q130_CREW_CAPACITY_SENSOR", "Minimal crew/capacity sensor", "OFFICE", "GATED", "PROTOTYPE",
       ("Q120_OFFICE_SENSOR_RESEARCH",), "Prototype low-friction workforce availability/hours/current-work capture with proportional privacy."),
    _q("Q140_CONTRACTOR_DNA_V1", "Contractor DNA v1", "DNA", "GATED", "PROTOTYPE",
       ("Q100_OUTCOME_GRAPH_V1", "Q130_CREW_CAPACITY_SENSOR"), "Learn operational truth from predicted versus actual productivity, duration, margin and capacity behaviour."),
    _q("Q150_SHADOW_PORTFOLIO_RESEARCH", "SHADOW portfolio-optimisation research", "SHADOW", "GATED", "RESEARCH",
       ("Q090_COMPANY_STATE_CONTRACT", "Q140_CONTRACTOR_DNA_V1"), "Validate scenario inputs, constraints and usefulness before building a probabilistic contractor twin."),
    _q("Q160_SHADOW_PORTFOLIO_PROTOTYPE", "SHADOW portfolio optimiser prototype", "SHADOW", "GATED", "PROTOTYPE",
       ("Q150_SHADOW_PORTFOLIO_RESEARCH",), "Compare opportunity combinations across cash, workforce, equipment, mobilisation, management capacity and risk."),
    _q("Q170_COMMAND_NEXT_BEST_ACTION", "COMMAND next-best-action engine v1", "COMMAND", "GATED", "PROTOTYPE",
       ("Q080_EVIDENCE_GRAPH_V1", "Q110_DYNAMIC_ELIGIBILITY_RESEARCH", "Q160_SHADOW_PORTFOLIO_PROTOTYPE"),
       "Move from ranked information to a few quantified, evidence-backed next decisions."),
    _q("Q180_ACTION_ARCHITECTURE", "ACTION execution architecture", "ACTION", "GATED", "RESEARCH",
       ("Q170_COMMAND_NEXT_BEST_ACTION",), "Define authorization, consent, audit, revocation and rollback boundaries before high-value external action."),
    _q("Q190_FUTURE_DEMAND_ASSET_CLOCK", "Future Demand Engine / Asset Clock research", "SIGNAL", "GATED", "RESEARCH",
       ("Q020_SIGNAL_CONTRACT_V1", "Q080_EVIDENCE_GRAPH_V1"), "Test whether asset lifecycle/public data predicts physical work early enough to create commercial action."),
    _q("Q200_FORCED_DEMAND", "Forced Demand / Obligation-to-Opportunity research", "SIGNAL", "GATED", "RESEARCH",
       ("Q020_SIGNAL_CONTRACT_V1", "Q080_EVIDENCE_GRAPH_V1"), "Validate rule-to-asset-to-work translation with legal traceability before LAW → BILL OF WORKS claims."),
    _q("Q210_SUPPLY_EDGE", "Supply Edge / Bid-to-Supply Intelligence research", "ACTION", "GATED", "RESEARCH",
       ("Q090_COMPANY_STATE_CONTRACT", "Q160_SHADOW_PORTFOLIO_PROTOTYPE", "Q180_ACTION_ARCHITECTURE"),
       "Validate BoQ/spec extraction, technical equivalence, installed/landed/cash-adjusted cost and supplier discovery before automating procurement."),
    _q("Q212_TRUSTBRIDGE_RESEARCH", "TrustBridge bilateral trade-confidence research", "DNA", "GATED", "RESEARCH",
       ("Q080_EVIDENCE_GRAPH_V1", "Q100_OUTCOME_GRAPH_V1", "Q180_ACTION_ARCHITECTURE", "Q210_SUPPLY_EDGE"),
       "Validate lawful KYB/payment/delivery evidence, Trade and Supplier Passports, transaction confidence and licensed credit/insurance orchestration by jurisdiction."),
    _q("Q214_TRADE_AGENT_ARCHITECTURE", "ObraSignal Trade Agent authorization and negotiation architecture", "ACTION", "GATED", "RESEARCH",
       ("Q180_ACTION_ARCHITECTURE", "Q210_SUPPLY_EDGE", "Q212_TRUSTBRIDGE_RESEARCH"),
       "Define explicit digital-agent identity plus Levels 0–4, scoped authority, negotiation limits and hard prevention of unauthorized legal/financial commitments."),
    _q("Q216_SUPPLIER_PORTAL", "Low-friction secure Supplier Portal prototype", "ACTION", "GATED", "PROTOTYPE",
       ("Q214_TRADE_AGENT_ARCHITECTURE",), "Let suppliers answer scoped RFQs without subscription while preserving least disclosure, audit, expiry/revocation and safe document handling."),
    _q("Q218_TRADE_LOOP_PILOT", "Integrated Supply Edge + TrustBridge + Trade Agent pilot", "ACTION", "GATED", "PILOT",
       ("Q160_SHADOW_PORTFOLIO_PROTOTYPE", "Q170_COMMAND_NEXT_BEST_ACTION", "Q210_SUPPLY_EDGE", "Q212_TRUSTBRIDGE_RESEARCH", "Q214_TRADE_AGENT_ARCHITECTURE", "Q216_SUPPLIER_PORTAL"),
       "Pilot Opportunity→BoQ→supplier→RFQ→terms→trust→SHADOW→negotiation→recommendation with 2–5 decisions and measurable economics, not supplier lists."),
    _q("Q220_WORK_PACKAGE_RELEASE", "Work Package Release Prediction research", "SIGNAL", "GATED", "RESEARCH",
       ("Q020_SIGNAL_CONTRACT_V1", "Q100_OUTCOME_GRAPH_V1"), "Test whether package timing, prime identity and subcontract release windows can be predicted accurately enough for action."),
    _q("Q230_VALUE_CREATED", "Measured and estimated Value Created framework", "COMMAND", "GATED", "PROTOTYPE",
       ("Q100_OUTCOME_GRAPH_V1", "Q170_COMMAND_NEXT_BEST_ACTION", "Q218_TRADE_LOOP_PILOT"),
       "Quantify legitimate opportunity, sourcing, liquidity, risk-avoidance and time-saving value without fabricated ROI."),
    _q("Q240_GROWTH_SIMULATOR", "Contractor Growth Simulator", "SHADOW", "GATED", "RESEARCH",
       ("Q160_SHADOW_PORTFOLIO_PROTOTYPE", "Q110_DYNAMIC_ELIGIBILITY_RESEARCH"), "Evaluate what the contractor should become only after constraints and portfolio economics are credible."),
    _q("Q250_RESCUE_MODE", "Rescue Mode / Rescue Signal research", "SIGNAL", "GATED", "RESEARCH",
       ("Q020_SIGNAL_CONTRACT_V1", "Q130_CREW_CAPACITY_SENSOR"), "Explore urgent post-award replacement/capacity demand only when supply and availability are trustworthy."),
    _q("Q260_BENCHMARK_NETWORK", "Privacy-preserving benchmark network", "DNA", "FUTURE", "RESEARCH",
       ("Q140_CONTRACTOR_DNA_V1", "Q230_VALUE_CREATED"), "Requires cohort size, anonymisation thresholds and competition/privacy safeguards."),
    _q("Q270_LIVE_CAPACITY_NETWORK", "Live Capacity Network", "ACTION", "FUTURE", "RESEARCH",
       ("Q130_CREW_CAPACITY_SENSOR", "Q180_ACTION_ARCHITECTURE", "Q260_BENCHMARK_NETWORK"), "Do not build a marketplace before verified capacity, trust and sufficient network density exist."),
    _q("Q280_CHAIN_REACTION", "Chain-Reaction Intelligence research", "SIGNAL", "FUTURE", "RESEARCH",
       ("Q190_FUTURE_DEMAND_ASSET_CLOCK",), "Second- and third-order demand remains a hypothesis until precision and actionability are demonstrated."),
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


def executable_after_current() -> tuple[ExecutionItem, ...]:
    """Return dependency-ready items in canonical queue order.

    Multiple items may technically be ready, but their order here remains the
authoritative priority order. Call ``next_item_after_current`` when choosing
what to execute; never create parallel execution plans from this tuple.
    """
    completed = {item.id for item in MASTER_EXECUTION_QUEUE if item.state == "DONE"}
    completed.add(CURRENT_ITEM_ID)
    return tuple(
        item for item in MASTER_EXECUTION_QUEUE
        if item.state in {"QUEUED", "GATED", "FUTURE"}
        and all(dep in completed for dep in item.dependencies)
    )


def next_executable_after_current() -> tuple[ExecutionItem, ...]:
    return executable_after_current()


def next_item_after_current() -> ExecutionItem | None:
    ready = executable_after_current()
    return ready[0] if ready else None
