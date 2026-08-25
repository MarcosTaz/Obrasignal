"""Single canonical execution queue for ObraSignal.

Every significant market, architecture, product, research or intelligence item
must enter this ordered queue. Supporting roadmaps may describe a domain but may
not create an independent execution order.

Exactly one item is ACTIVE. Dependencies determine readiness; queue order decides
which ready item executes next. GATED and FUTURE items require explicit promotion
before they can enter automatic execution.
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
CURRENT_ITEM_ID = "Q060_CHILE_MERCADOPUBLICO"

MASTER_EXECUTION_QUEUE = (
    _q("Q000_SCOPE_REBASE", "International market-scope rebase", "STRATEGY", "DONE", "PRODUCTION",
       reason="Active coverage fixed at 45 markets; bespoke development is BUILD-only."),
    _q("Q005_MODULAR_ARCHITECTURE_GUARDRAILS", "Modular monolith and replaceable-capability architecture guardrails", "ARCHITECTURE", "DONE", "PRODUCTION",
       ("Q000_SCOPE_REBASE",),
       "Adopt small stable Core, contract-first replaceable capabilities, canonical data/events, capability registry, feature flags, failure isolation, contextual UX and architecture fitness tests without premature microservices. This is a cross-cutting rule, not a parallel roadmap."),
    _q("Q010_BR_PNCP_DISCOVERY", "Brazil PNCP national PCA discovery contract", "SIGNAL", "DONE", "RESEARCH",
       ("Q000_SCOPE_REBASE",),
       "Publisher-native Works categories, public national discovery, pagination, identity, update timestamp and recent-first ordering were live-proven."),
    _q("Q020_SIGNAL_CONTRACT_V1", "Generic provenance-first Signal contract and persistence", "SIGNAL", "DONE", "PRODUCTION",
       ("Q000_SCOPE_REBASE",),
       "Signal persistence is durable and transactional; explicit non-TENDER records can no longer masquerade as legacy tenders."),
    _q("Q030_BR_PNCP_PCA", "Brazil PNCP construction procurement-plan connector", "SIGNAL", "GATED", "PRODUCTION",
       ("Q010_BR_PNCP_DISCOVERY", "Q020_SIGNAL_CONTRACT_V1"),
       "Connector/tests are prebuilt but production promotion is blocked: isolated live smokes repeatedly failed on PNCP transport reliability, including five bounded attempts ending in connect timeout. Reopen only after stable live production-path validation."),
    _q("Q040_CANADA_BUYS", "CanadaBuys federal construction connector", "SIGNAL", "DONE", "PRODUCTION",
       ("Q020_SIGNAL_CONTRACT_V1",),
       "Official federal construction contract, identity/amendment/lifecycle semantics, exact schema, opt-in production wiring, exact-head CI and live production-path validation completed."),
    _q("Q045_TRIAL_POLICY_V01", "21-day value-aware evaluation and enterprise pilot policy v0.1", "STRATEGY", "DONE", "PRODUCTION",
       ("Q040_CANADA_BUYS",),
       "Replace signup-clock legacy trial for new accounts with auditable value-aware activation, preserve legacy accounts and RevenueCat paid precedence; policy remains VALIDATION REQUIRED and does not block the canonical market-coverage queue."),
    _q("Q050_US_SAM", "SAM.gov federal construction opportunities connector", "SIGNAL", "DONE", "PRODUCTION",
       ("Q020_SIGNAL_CONTRACT_V1",),
       "Official public Contract Opportunities bulk path validated: strict 47-column schema, NAICS 23 construction admission, NoticeId identity, opt-in runtime wiring, fail-closed disappearance semantics, exact-head CI and live production-path proof."),
    _q("Q060_CHILE_MERCADOPUBLICO", "Chile Mercado Público construction connector", "SIGNAL", "ACTIVE", "PRODUCTION",
       ("Q020_SIGNAL_CONTRACT_V1",), "Strong official API and favourable value-to-effort ratio."),
    _q("Q070_SHARED_FAMILIES", "Harden TED/eForms and OCDS shared-coverage families", "SIGNAL", "QUEUED", "PRODUCTION",
       ("Q040_CANADA_BUYS", "Q050_US_SAM", "Q060_CHILE_MERCADOPUBLICO"),
       "Maximise supported markets per maintained connector and remove country-specific duplication; a blocked Brazil source must not freeze unrelated shared coverage."),
    _q("Q080_EVIDENCE_GRAPH_V1", "Proof / Evidence Graph v1", "COMMAND", "QUEUED", "PRODUCTION",
       ("Q020_SIGNAL_CONTRACT_V1",),
       "Material recommendations need traceable WHY / SHOW ME / WHAT IF evidence before higher autonomy is safe."),
    _q("Q090_COMPANY_STATE_CONTRACT", "Company operational-state contract", "OFFICE", "QUEUED", "PROTOTYPE",
       ("Q080_EVIDENCE_GRAPH_V1",),
       "Define the minimum internal facts needed for capacity/economics without building a generic ERP."),
    _q("Q100_OUTCOME_GRAPH_V1", "Outcome Graph and decision-result capture", "DNA", "QUEUED", "PROTOTYPE",
       ("Q080_EVIDENCE_GRAPH_V1", "Q090_COMPANY_STATE_CONTRACT"),
       "Win/loss/no-bid and predicted-vs-actual outcomes are prerequisites for Contractor DNA and regret learning."),
    _q("Q110_DYNAMIC_ELIGIBILITY_RESEARCH", "Dynamic Eligibility / Opportunity Unlock research", "COMMAND", "QUEUED", "RESEARCH",
       ("Q090_COMPANY_STATE_CONTRACT",),
       "Test whether resource, qualification, partner, capital and guarantee blockers can be legally and economically unlocked."),
    _q("Q120_OFFICE_SENSOR_RESEARCH", "OFFICE sensor architecture and integrate-vs-build audit", "OFFICE", "QUEUED", "RESEARCH",
       ("Q090_COMPANY_STATE_CONTRACT",),
       "Select only operational inputs that improve decisions; integrate generic software instead of rebuilding it."),
    _q("Q130_CREW_CAPACITY_SENSOR", "Minimal crew/capacity sensor", "OFFICE", "GATED", "PROTOTYPE",
       ("Q120_OFFICE_SENSOR_RESEARCH",),
       "Prototype low-friction workforce availability/hours/current-work capture with proportional privacy."),
    _q("Q140_CONTRACTOR_DNA_V1", "Contractor DNA v1", "DNA", "GATED", "PROTOTYPE",
       ("Q100_OUTCOME_GRAPH_V1", "Q130_CREW_CAPACITY_SENSOR"),
       "Learn operational truth from predicted versus actual productivity, duration, margin and capacity behaviour."),
    _q("Q150_SHADOW_PORTFOLIO_RESEARCH", "SHADOW portfolio-optimisation research", "SHADOW", "GATED", "RESEARCH",
       ("Q090_COMPANY_STATE_CONTRACT", "Q140_CONTRACTOR_DNA_V1"),
       "Validate scenario inputs, constraints and decision usefulness before building a probabilistic contractor twin."),
    _q("Q160_SHADOW_PORTFOLIO_PROTOTYPE", "SHADOW portfolio optimiser prototype", "SHADOW", "GATED", "PROTOTYPE",
       ("Q150_SHADOW_PORTFOLIO_RESEARCH",),
       "Compare opportunity combinations across cash, workforce, equipment, mobilisation, management capacity and risk."),
    _q("Q170_COMMAND_NEXT_BEST_ACTION", "COMMAND next-best-action engine v1", "COMMAND", "GATED", "PROTOTYPE",
       ("Q080_EVIDENCE_GRAPH_V1", "Q110_DYNAMIC_ELIGIBILITY_RESEARCH", "Q160_SHADOW_PORTFOLIO_PROTOTYPE"),
       "Move from ranked information to a few quantified, evidence-backed next decisions."),
    _q("Q180_ACTION_ARCHITECTURE", "ACTION execution architecture", "ACTION", "GATED", "RESEARCH",
       ("Q170_COMMAND_NEXT_BEST_ACTION",),
       "Define authorisation, consent, audit, revocation and rollback boundaries before high-value external action."),
    _q("Q190_FUTURE_DEMAND_ASSET_CLOCK", "Future Demand Engine / Asset Clock research", "SIGNAL", "GATED", "RESEARCH",
       ("Q020_SIGNAL_CONTRACT_V1", "Q080_EVIDENCE_GRAPH_V1"),
       "Test whether asset lifecycle/public data predicts physical work early enough to create commercial action."),
    _q("Q200_FORCED_DEMAND", "Forced Demand / Obligation-to-Opportunity research", "SIGNAL", "GATED", "RESEARCH",
       ("Q020_SIGNAL_CONTRACT_V1", "Q080_EVIDENCE_GRAPH_V1"),
       "Validate rule-to-asset-to-work translation with legal traceability before LAW → BILL OF WORKS claims."),
    _q("Q210_SUPPLY_EDGE", "Supply Edge / Bid-to-Supply Intelligence research", "ACTION", "GATED", "RESEARCH",
       ("Q090_COMPANY_STATE_CONTRACT", "Q160_SHADOW_PORTFOLIO_PROTOTYPE", "Q180_ACTION_ARCHITECTURE"),
       "Validate BoQ/spec extraction, technical equivalence, installed/landed/cash-adjusted cost and supplier discovery before automating procurement."),
    _q("Q212_TRUSTBRIDGE_RESEARCH", "TrustBridge bilateral trade-confidence research", "DNA", "GATED", "RESEARCH",
       ("Q080_EVIDENCE_GRAPH_V1", "Q100_OUTCOME_GRAPH_V1", "Q180_ACTION_ARCHITECTURE", "Q210_SUPPLY_EDGE"),
       "Validate lawful KYB/payment/delivery evidence, Trade and Supplier Passports, transaction confidence and licensed credit/insurance orchestration by jurisdiction."),
    _q("Q214_TRADE_AGENT_ARCHITECTURE", "ObraSignal Trade Agent authorization and negotiation architecture", "ACTION", "GATED", "RESEARCH",
       ("Q180_ACTION_ARCHITECTURE", "Q210_SUPPLY_EDGE", "Q212_TRUSTBRIDGE_RESEARCH"),
       "Define explicit digital-agent identity, Levels 0–4, scoped authority, negotiation limits and hard prevention of unauthorized legal/financial commitments."),
    _q("Q216_SUPPLIER_PORTAL", "Low-friction secure Supplier Portal prototype", "ACTION", "GATED", "PROTOTYPE",
       ("Q214_TRADE_AGENT_ARCHITECTURE",),
       "Let suppliers answer scoped RFQs without subscription while preserving least disclosure, audit, expiry/revocation and safe document handling."),
    _q("Q218_TRADE_LOOP_PILOT", "Integrated Supply Edge + TrustBridge + Trade Agent pilot", "ACTION", "GATED", "PILOT",
       ("Q160_SHADOW_PORTFOLIO_PROTOTYPE", "Q170_COMMAND_NEXT_BEST_ACTION", "Q210_SUPPLY_EDGE", "Q212_TRUSTBRIDGE_RESEARCH", "Q214_TRADE_AGENT_ARCHITECTURE", "Q216_SUPPLIER_PORTAL"),
       "Pilot opportunity→BoQ→supplier→RFQ→terms→trust→SHADOW→negotiation→recommendation with 2–5 decisions and measurable economics, not supplier lists."),
    _q("Q220_WORK_PACKAGE_RELEASE", "Work Package Release Prediction research", "SIGNAL", "GATED", "RESEARCH",
       ("Q020_SIGNAL_CONTRACT_V1", "Q100_OUTCOME_GRAPH_V1"),
       "Test whether package timing, prime identity and subcontract release windows can be predicted accurately enough for action."),
    _q("Q222_MOBILIZE_RESEARCH", "ObraSignal MOBILIZE integrated mobilization-intelligence research", "SHADOW", "GATED", "RESEARCH",
       ("Q090_COMPANY_STATE_CONTRACT", "Q160_SHADOW_PORTFOLIO_PROTOTYPE", "Q180_ACTION_ARCHITECTURE", "Q210_SUPPLY_EDGE"),
       "Compare daily travel, accommodation, hybrid transport, own-vs-local vehicles and contextual local services using MINIMUM/PROBABLE/PRUDENT economics, provenance and direct margin impact rather than isolated travel calculators."),
    _q("Q224_SITE_READY_RESEARCH", "ObraSignal SITE READY pre-mobilization readiness research", "COMMAND", "GATED", "RESEARCH",
       ("Q080_EVIDENCE_GRAPH_V1", "Q090_COMPANY_STATE_CONTRACT", "Q180_ACTION_ARCHITECTURE", "Q222_MOBILIZE_RESEARCH"),
       "Validate useful project-specific blockers, evidence-backed readiness and delay risk while controlling false positives; avoid decorative scores and generic checklists."),
    _q("Q226_CAPACITY_OPTIMIZER_RESEARCH", "Capacity Acquisition Optimizer research", "SHADOW", "GATED", "RESEARCH",
       ("Q140_CONTRACTOR_DNA_V1", "Q160_SHADOW_PORTFOLIO_PROTOTYPE", "Q190_FUTURE_DEMAND_ASSET_CLOCK", "Q210_SUPPLY_EDGE", "Q222_MOBILIZE_RESEARCH"),
       "Compare MAKE/OWN, BUY, RENT, SUBCONTRACT, TEMPORARY and REDEPLOY using current economics, opportunity cost, residual value and probabilistic future utilization rather than one-project price alone."),
    _q("Q228_CREW_ECONOMICS_RESEARCH", "CREW ECONOMICS installed-cost configuration research", "DNA", "GATED", "RESEARCH",
       ("Q130_CREW_CAPACITY_SENSOR", "Q140_CONTRACTOR_DNA_V1", "Q160_SHADOW_PORTFOLIO_PROTOTYPE", "Q222_MOBILIZE_RESEARCH"),
       "Compare own/local/subcontract crew configurations across labour, travel, accommodation, productivity, supervision, schedule, quality and risk without optimizing wage/hour in isolation."),
    _q("Q229_DEAD_TIME_RESEARCH", "ObraSignal DEAD TIME idle-capacity research", "OFFICE", "GATED", "RESEARCH",
       ("Q120_OFFICE_SENSOR_RESEARCH", "Q130_CREW_CAPACITY_SENSOR", "Q140_CONTRACTOR_DNA_V1", "Q170_COMMAND_NEXT_BEST_ACTION", "Q222_MOBILIZE_RESEARCH", "Q224_SITE_READY_RESEARCH"),
       "Measure defensible idle cost and test economically better temporary uses of workers/equipment without invasive tracking or pretending downtime can be eliminated."),
    _q("Q231_CAPACITY_UNIT_SERVICES", "Capacity Unit and sellable-services contract", "OFFICE", "GATED", "PROTOTYPE",
       ("Q090_COMPANY_STATE_CONTRACT", "Q120_OFFICE_SENSOR_RESEARCH", "Q130_CREW_CAPACITY_SENSOR"),
       "Create one privacy-proportional abstraction for worker, crew, specialty, technical service, equipment and vehicle capacity without turning OFFICE into HR, fleet or marketplace software."),
    _q("Q232_MICROWORKS_SOURCE_VALIDATION", "MicroWorks and services source-family validation", "SIGNAL", "GATED", "RESEARCH",
       ("Q020_SIGNAL_CONTRACT_V1", "Q080_EVIDENCE_GRAPH_V1", "Q231_CAPACITY_UNIT_SERVICES"),
       "Validate lawful official/local/private/network source families, incremental freshness, lifecycle/filled detection, reuse rights and sufficient commercially relevant volume before building a small-work feed."),
    _q("Q233_MICROWORKS_ECONOMIC_MATCHING", "MicroWorks economic matching and idle-capacity recovery model", "COMMAND", "GATED", "PROTOTYPE",
       ("Q160_SHADOW_PORTFOLIO_PROTOTYPE", "Q170_COMMAND_NEXT_BEST_ACTION", "Q212_TRUSTBRIDGE_RESEARCH", "Q222_MOBILIZE_RESEARCH", "Q229_DEAD_TIME_RESEARCH", "Q231_CAPACITY_UNIT_SERVICES", "Q232_MICROWORKS_SOURCE_VALIDATION"),
       "Rank the best use of a real capacity window using contribution, mobilization, fatigue, risk, requester confidence and opportunity cost; DO NOTHING must remain a valid best decision."),
    _q("Q234_CONTINUOUS_OPPORTUNITY_HUNTING", "Continuous Opportunity Hunting and Auto-Hunt policies", "ACTION", "GATED", "PROTOTYPE",
       ("Q120_OFFICE_SENSOR_RESEARCH", "Q180_ACTION_ARCHITECTURE", "Q229_DEAD_TIME_RESEARCH", "Q233_MICROWORKS_ECONOMIC_MATCHING"),
       "Turn OFFICE/SHADOW capacity events into policy-bounded, source-safe incremental searches with notification discipline; capacity creates search, but never unauthorized commitment or noisy polling."),
    _q("Q235_MICROWORKS_ACTION_PILOT", "MicroWorks Rapid Quote and low-risk Action pilot", "ACTION", "GATED", "PILOT",
       ("Q214_TRADE_AGENT_ARCHITECTURE", "Q233_MICROWORKS_ECONOMIC_MATCHING", "Q234_CONTINUOUS_OPPORTUNITY_HUNTING"),
       "Pilot request clarification, photo/description triage, minimum economic price, rapid quote, contact and scheduling inside explicit authority; prove realized economics, low admin and no harm to core projects."),
    _q("Q230_VALUE_CREATED", "Measured and estimated Value Created framework", "COMMAND", "GATED", "PROTOTYPE",
       ("Q100_OUTCOME_GRAPH_V1", "Q170_COMMAND_NEXT_BEST_ACTION"),
       "Quantify legitimate opportunity, sourcing, mobilization, liquidity, risk-avoidance and idle-capacity recovery value without fabricated ROI or double counting."),
    _q("Q237_TRANSACTION_MONETIZATION_ARCHITECTURE", "Trust-aligned ancillary revenue and transaction monetization architecture", "STRATEGY", "GATED", "RESEARCH",
       ("Q218_TRADE_LOOP_PILOT", "Q235_MICROWORKS_ACTION_PILOT", "Q230_VALUE_CREATED"),
       "Preserve modular Quote/Supplier/Transaction/Referral/Partner/Commission/FinancingRoute/InsuranceRoute/Booking/Conversion contracts and test SaaS→transaction→partner→network monetization only after measurable customer value. No pay-to-rank; commercial compensation must be technically separated from recommendation economics, auditable, disclosure-capable and legally gated."),
    _q("Q240_GROWTH_SIMULATOR", "Contractor Growth Simulator", "SHADOW", "GATED", "RESEARCH",
       ("Q160_SHADOW_PORTFOLIO_PROTOTYPE", "Q110_DYNAMIC_ELIGIBILITY_RESEARCH"),
       "Evaluate what the contractor should become only after constraints and portfolio economics are credible."),
    _q("Q250_RESCUE_MODE", "Rescue Mode / Rescue Signal research", "SIGNAL", "GATED", "RESEARCH",
       ("Q020_SIGNAL_CONTRACT_V1", "Q130_CREW_CAPACITY_SENSOR"),
       "Explore urgent post-award replacement/capacity demand only when supply and availability are trustworthy; reuse MicroWorks urgency/matching infrastructure when mature."),
    _q("Q260_BENCHMARK_NETWORK", "Privacy-preserving benchmark network", "DNA", "FUTURE", "RESEARCH",
       ("Q140_CONTRACTOR_DNA_V1", "Q230_VALUE_CREATED"),
       "Requires cohort size, anonymisation thresholds and competition/privacy safeguards."),
    _q("Q270_LIVE_CAPACITY_NETWORK", "Live Capacity Network", "ACTION", "FUTURE", "RESEARCH",
       ("Q130_CREW_CAPACITY_SENSOR", "Q180_ACTION_ARCHITECTURE", "Q212_TRUSTBRIDGE_RESEARCH", "Q231_CAPACITY_UNIT_SERVICES", "Q260_BENCHMARK_NETWORK"),
       "Do not build a reverse marketplace before verified capacity, trust and sufficient network density exist; publish only minimal authorized capacity context."),
    _q("Q280_CHAIN_REACTION", "Chain-Reaction Intelligence research", "SIGNAL", "FUTURE", "RESEARCH",
       ("Q190_FUTURE_DEMAND_ASSET_CLOCK",),
       "Second- and third-order demand remains a hypothesis until precision and actionability are demonstrated."),
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
    """Return only dependency-ready QUEUED items in canonical order.

    The current ACTIVE item is treated as hypothetically complete solely to
    answer "what comes next?". GATED items require an explicit gate-reopen
    decision and FUTURE items require explicit promotion; neither can enter
    automatic execution merely because their dependencies happen to be complete.
    """
    completed = {item.id for item in MASTER_EXECUTION_QUEUE if item.state == "DONE"}
    completed.add(CURRENT_ITEM_ID)
    return tuple(
        item for item in MASTER_EXECUTION_QUEUE
        if item.state == "QUEUED"
        and all(dep in completed for dep in item.dependencies)
    )


def next_executable_after_current() -> tuple[ExecutionItem, ...]:
    """Backward-compatible alias for callers created with queue v1."""
    return executable_after_current()


def next_item_after_current() -> ExecutionItem | None:
    ready = executable_after_current()
    return ready[0] if ready else None
