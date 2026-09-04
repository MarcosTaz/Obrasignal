from __future__ import annotations

from flask import g, jsonify, request

from .csv_import import commit_csv_import, preview_csv_facts
from .evidence import EvidenceKind, EvidenceSource


_PREVIEW_FORM_FIELDS = {"evidence_id"}
_COMMIT_FORM_FIELDS = {
    "evidence_id",
    "kind",
    "display_name",
    "external_ref",
    "captured_at",
}


def _form_value(key, *, max_len=500):
    value = request.form.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    value = value.strip()
    if len(value) > max_len or "\x00" in value:
        raise ValueError(f"{key} is invalid")
    return value


def _strict_form(allowed):
    unknown = set(request.form) - set(allowed)
    if unknown:
        raise ValueError(f"unknown form fields: {sorted(unknown)}")
    missing = set(allowed) - set(request.form)
    if missing:
        raise ValueError(f"missing form fields: {sorted(missing)}")
    if set(request.files) != {"file"}:
        raise ValueError("multipart upload must contain exactly one file field named file")


def _uploaded_bytes():
    uploaded = request.files.get("file")
    if uploaded is None:
        raise ValueError("file is required")
    content = uploaded.read()
    if not isinstance(content, bytes):
        raise ValueError("uploaded file could not be read as bytes")
    return content


def _preview_payload(preview):
    return {
        "sha256": preview.sha256,
        "row_count": preview.row_count,
        "facts": [
            {
                "fact_id": item.fact_id,
                "evidence_id": item.evidence_id,
                "fact_type": item.fact_type.value,
                "raw_value": item.raw_value,
                "normalized_value": item.normalized_value,
                "scope_ref": item.scope_ref,
                "page_ref": item.page_ref,
                "clause_ref": item.clause_ref,
                "review_state": item.review_state.value,
            }
            for item in preview.facts
        ],
        "truth_rule": "preview validates structure only; every imported fact remains UNREVIEWED",
    }


def register_csv_import_routes(app, repository):
    @app.route("/api/capacity/evidence/import/csv/preview", methods=["POST"])
    def preview_csv_import():
        _strict_form(_PREVIEW_FORM_FIELDS)
        evidence_id = _form_value("evidence_id", max_len=200)
        preview = preview_csv_facts(
            _uploaded_bytes(),
            tenant_id=g.capacity_tenant_id,
            evidence_id=evidence_id,
        )
        return jsonify(_preview_payload(preview))

    @app.route("/api/capacity/evidence/import/csv", methods=["POST"])
    def import_csv_evidence():
        if request.headers.get("X-Capacity-Intent") != "import-csv-evidence":
            return jsonify({"error": "csv_import_intent_required"}), 403
        _strict_form(_COMMIT_FORM_FIELDS)
        evidence_id = _form_value("evidence_id", max_len=200)
        content = _uploaded_bytes()
        preview = preview_csv_facts(
            content,
            tenant_id=g.capacity_tenant_id,
            evidence_id=evidence_id,
        )
        try:
            kind = EvidenceKind(_form_value("kind", max_len=40))
        except ValueError as exc:
            raise ValueError("kind must be a valid EvidenceKind") from exc
        source = EvidenceSource(
            tenant_id=g.capacity_tenant_id,
            evidence_id=evidence_id,
            kind=kind,
            display_name=_form_value("display_name", max_len=300),
            external_ref=_form_value("external_ref", max_len=500),
            sha256=preview.sha256,
            captured_at=_form_value("captured_at", max_len=80),
        )
        try:
            source_created, inserted = commit_csv_import(
                db_path=repository.db_path,
                source=source,
                preview=preview,
            )
        except FileExistsError as exc:
            return jsonify({"error": "csv_import_conflict", "detail": str(exc)}), 409
        return jsonify(
            {
                "source_created": source_created,
                "facts_inserted": inserted,
                "sha256": preview.sha256,
                "row_count": preview.row_count,
                "review_state": "UNREVIEWED",
                "raw_content_retained": False,
                "source_external_ref": source.external_ref,
                "truth_rule": "CSV bytes were validated for ingestion; the external_ref must remain the durable original source",
            }
        ), 201 if source_created or inserted else 200

    return app
