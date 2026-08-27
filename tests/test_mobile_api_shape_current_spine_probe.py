"""Current-spine producer→consumer shape acceptance for core mobile reads/writes."""
from pathlib import Path


def _text(path):
    return Path(path).read_text(encoding="utf-8")


def test_opportunity_list_envelope_and_mobile_consumer_agree():
    producer = _text("api.py")
    mobile = _text("mobile/src/api.js")
    assert 'return jsonify({"items": items, "count": len(items), "market": market, "source_coverage": contract["summary"], "source_health_contract_version": contract["contract_version"], "empty_result": empty_context, "generated_at": _iso_now(), "account_id": identity.account_id})' in producer
    assert 'const data=await readWhenReady(`/opportunities?${p.toString()}`);return data?{...data,items:(data.items||[]).map(normalizeOpportunity)}:data;' in mobile


def test_opportunity_detail_is_direct_item_and_mobile_does_not_unwrap_wrong_envelope():
    producer = _text("api.py")
    mobile = _text("mobile/src/api.js")
    assert "return jsonify(item)" in producer
    assert 'opportunity:async(id)=>normalizeOpportunity(await readWhenReady(`/opportunities/${encodeURIComponent(id)}`))' in mobile


def test_stats_shape_matches_mobile_direct_metric_consumption_and_keeps_unknown_visible():
    producer = _text("api.py")
    mobile_app = _text("mobile/App.js")
    assert 'return jsonify({"total": total, "high": high, "open": open_count, "new24": new24' in producer
    assert "function metricText(value){return isKnown(value)?String(value):'—'}" in mobile_app
    assert "[['Oportunidades',stats.total],['Abertas',stats.open],['Novas 24h',stats.new24],['Alta relevância',stats.high]]" in mobile_app


def test_workflow_get_post_nested_envelope_matches_auth_and_mobile_consumers():
    producer = _text("api.py")
    mobile = _text("mobile/App.js")
    auth = _text(".github/workflows/authenticated-e2e.yml")
    assert 'return jsonify({"workflow": workflow, "account_id": identity.account_id, "generated_at": _iso_now()})' in producer
    assert 'return jsonify({"ok": True, "workflow": workflow, "account_id": identity.account_id, "generated_at": _iso_now()})' in producer
    assert "const workflow=response?.workflow||response" in mobile
    assert "workflow=workflow_payload.get('workflow')" in auth
    assert "workflow_payload.get('status')" not in auth


def test_workflow_stats_shape_matches_authenticated_consumer():
    producer = _text("api.py")
    auth = _text(".github/workflows/authenticated-e2e.yml")
    assert 'return jsonify({"counts": counts, "account_id": identity.account_id, "generated_at": _iso_now()})' in producer
    assert "assert workflow.get('account_id') == opportunities['account_id']" in auth
    assert "assert isinstance(workflow.get('counts'), dict)" in auth
