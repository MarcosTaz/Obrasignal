from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from factory_cloud.assurance_store import AssuranceStoreError


ALLOWED_FINDING_STATES = {
    "UNRESOLVED_EVIDENCE",
    "READY_FOR_REVIEW",
    "APPROVED",
    "REJECTED",
    "ACTIONED",
    "RECOVERED",
    "CLOSED_NO_RECOVERY",
}


@dataclass(frozen=True)
class FindingQueueItem:
    finding_id: str
    state: str
    net_potential: str
    currency_unit: str | None
    creator_actor: str
    created_at: str
    reviewer: str | None
    decision_reason: str | None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


class IndustrialClaimsReadModel:
    """Tenant-scoped, bounded read model for assisted reviewer/operator queues.

    This view exposes workflow state and calculation outcome only. It never
    returns raw documentary content or evidence metadata payloads.
    """

    def __init__(self, database: str | Path):
        self.path = Path(database)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def list_findings(
        self,
        *,
        tenant_id: str,
        states: tuple[str, ...],
        limit: int = 100,
    ) -> tuple[FindingQueueItem, ...]:
        tenant = tenant_id.strip()
        if not tenant:
            raise AssuranceStoreError("tenant_id is required")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 100:
            raise AssuranceStoreError("finding queue limit must be an integer from 1 to 100")

        normalized_states = tuple(dict.fromkeys(str(state).strip().upper() for state in states if str(state).strip()))
        if not normalized_states:
            return ()
        unknown_states = set(normalized_states) - ALLOWED_FINDING_STATES
        if unknown_states:
            raise AssuranceStoreError("unsupported finding queue state")

        placeholders = ",".join("?" for _ in normalized_states)
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT f.*, a.actor_id AS creator_actor, a.occurred_at AS created_at
                    FROM findings f
                    JOIN audit_events a
                      ON a.tenant_id=f.tenant_id
                     AND a.subject_ref=f.finding_id
                     AND a.event_type='industrial_finding_created'
                    WHERE f.tenant_id=?
                      AND f.finding_type='industrial_recovery_candidate'
                      AND f.state IN ({placeholders})
                    ORDER BY a.occurred_at DESC, f.finding_id DESC
                    LIMIT ?""",
                (tenant, *normalized_states, limit),
            ).fetchall()

            items: list[FindingQueueItem] = []
            for row in rows:
                try:
                    calculation_ids = json.loads(row["calculation_ids_json"])
                except (TypeError, ValueError) as exc:
                    raise AssuranceStoreError("finding queue calculation lineage is invalid") from exc
                if not isinstance(calculation_ids, list) or len(calculation_ids) != 1:
                    raise AssuranceStoreError("industrial finding queue requires exactly one calculation")
                calculation = conn.execute(
                    """SELECT formula_id,output_value,output_unit
                       FROM calculations
                       WHERE tenant_id=? AND calculation_id=?""",
                    (tenant, str(calculation_ids[0])),
                ).fetchone()
                if calculation is None or calculation["formula_id"] != "industrial_net_potential_claim":
                    raise AssuranceStoreError("industrial finding queue calculation not found")
                creator = str(row["creator_actor"] or "").strip()
                created_at = str(row["created_at"] or "").strip()
                if not creator or not created_at:
                    raise AssuranceStoreError("industrial finding queue creation audit is incomplete")
                items.append(
                    FindingQueueItem(
                        finding_id=str(row["finding_id"]),
                        state=str(row["state"]),
                        net_potential=str(calculation["output_value"]),
                        currency_unit=str(calculation["output_unit"]) if calculation["output_unit"] is not None else None,
                        creator_actor=creator,
                        created_at=created_at,
                        reviewer=str(row["reviewer"]) if row["reviewer"] is not None else None,
                        decision_reason=str(row["decision_reason"]) if row["decision_reason"] is not None else None,
                    )
                )
        return tuple(items)
