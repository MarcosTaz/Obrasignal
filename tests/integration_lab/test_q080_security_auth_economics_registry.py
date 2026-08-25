from capability_registry import capability
from capability_rollout import runtime_enabled


def test_execution_economics_registry_additions_do_not_promote_q080_or_siblings(monkeypatch):
    evidence = capability('EVIDENCE')
    bid = capability('BID_ECONOMICS')
    bangs = capability('BANGS')
    mobilize = capability('MOBILIZE')

    assert evidence.state == 'EXPERIMENT'
    assert evidence.contract_versions == ('evidence.v1-draft',)
    assert evidence.feature_flag == 'evidence_graph_v1'
    assert evidence.kill_switch_required is True

    assert bid.state == 'RESEARCH'
    assert bid.owner_domain == 'COMMAND'
    assert bid.feature_flag == 'bid_economics_v0'
    assert bid.kill_switch_required is True

    assert bangs.state == 'RESEARCH'
    assert bangs.owner_domain == 'SHADOW'
    assert bangs.feature_flag == 'bangs_field_intelligence_v0'
    assert bangs.kill_switch_required is True

    assert mobilize.state == 'RESEARCH'
    assert mobilize.owner_domain == 'SHADOW'

    monkeypatch.setenv('OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1', 'false')
    monkeypatch.setenv('OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1', 'false')
    assert runtime_enabled('EVIDENCE') is False


def test_q080_kill_switch_still_wins_after_economics_registry_union(monkeypatch):
    monkeypatch.setenv('OBRASIGNAL_FEATURE_EVIDENCE_GRAPH_V1', 'true')
    monkeypatch.setenv('OBRASIGNAL_KILL_EVIDENCE_GRAPH_V1', 'true')
    assert runtime_enabled('EVIDENCE') is False
