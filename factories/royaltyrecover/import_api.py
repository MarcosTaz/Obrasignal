from __future__ import annotations

from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from normalized_import import NormalizedSalesRow, import_sales_batch, list_sales_records
from repository import ConflictError, RoyaltyRepository


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid decimal") from exc
    if not parsed.is_finite():
        raise ValueError("decimal must be finite")
    return parsed


def create_import_blueprint(repository: RoyaltyRepository) -> Blueprint:
    bp = Blueprint("royaltyrecover_import", __name__)

    @bp.post("/api/v1/agreements/<agreement_id>/sales-imports")
    def import_sales(agreement_id):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "invalid_input", "detail": "JSON object required"}), 400
        raw_rows = data.get("rows")
        if not isinstance(raw_rows, list):
            return jsonify({"error": "invalid_input", "detail": "rows must be an array"}), 400
        try:
            rows = [
                NormalizedSalesRow(
                    source_row_key=str(item.get("source_row_key") or "") if isinstance(item, dict) else "",
                    transaction_date=str(item.get("transaction_date") or "") if isinstance(item, dict) else "",
                    gross_amount=_decimal(item.get("gross_amount")) if isinstance(item, dict) else None,
                    units=_decimal(item.get("units")) if isinstance(item, dict) else None,
                    currency=item.get("currency") if isinstance(item, dict) else None,
                )
                for item in raw_rows
            ]
            result = import_sales_batch(
                repository,
                request.royaltyrecover_org_id,
                agreement_id,
                str(data.get("source_system") or ""),
                str(data.get("source_dataset_id") or ""),
                rows,
                str(data.get("evidence_id") or ""),
                request.royaltyrecover_actor_id,
            )
        except ConflictError:
            # Preserve conflict semantics for duplicate source rows/datasets.
            # ConflictError subclasses ValueError, so it must bypass the generic
            # input handler and reach the application's canonical 409 handler.
            raise
        except (TypeError, ValueError) as exc:
            return jsonify({"error": "invalid_input", "detail": str(exc)}), 400
        return jsonify({
            "source_dataset_id": result.source_dataset_id,
            "source_system": result.source_system,
            "row_count": result.row_count,
            "dataset_sha256": result.dataset_sha256,
            "evidence_id": result.evidence_id,
            "raw_source_content_persisted": False,
        }), 201

    @bp.get("/api/v1/agreements/<agreement_id>/sales-records")
    def sales_records(agreement_id):
        source_dataset_id = request.args.get("source_dataset_id")
        return jsonify({"items": list_sales_records(repository, request.royaltyrecover_org_id, agreement_id, source_dataset_id)})

    return bp
