from pathlib import Path


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"missing promotion target: {label}")
    return text.replace(old, new, 1)


p = Path("master_execution_queue.py")
s = p.read_text()
s = replace_once(s, 'CURRENT_ITEM_ID = "Q070_SHARED_FAMILIES"', 'CURRENT_ITEM_ID = "Q080_EVIDENCE_GRAPH_V1"', "current item")
s = replace_once(
    s,
    '''    _q("Q070_SHARED_FAMILIES", "Harden TED/eForms and OCDS shared-coverage families", "SIGNAL", "ACTIVE", "PRODUCTION",
       ("Q040_CANADA_BUYS", "Q050_US_SAM"),
       "Maximise supported markets per maintained connector and remove country-specific duplication; country-specific external gates such as Brazil transport reliability or Chile credentials must not freeze independent shared-family hardening."),
    _q("Q080_EVIDENCE_GRAPH_V1", "Proof / Evidence Graph v1", "COMMAND", "QUEUED", "PRODUCTION",
       ("Q020_SIGNAL_CONTRACT_V1",),
       "Material recommendations need traceable WHY / SHOW ME / WHAT IF evidence before higher autonomy is safe."),
''',
    '''    _q("Q070_SHARED_FAMILIES", "Harden TED/eForms and OCDS shared-coverage families", "SIGNAL", "DONE", "PRODUCTION",
       ("Q040_CANADA_BUYS", "Q050_US_SAM"),
       "Canonical TED/eForms/OCDS family fitness registry, immutable architecture contracts, shared family runtime composition, runtime deduplication across Germany/Estonia/Ecuador/UK and exact-head Python+Mobile CI completed; materially different transports remain intentionally separate."),
    _q("Q080_EVIDENCE_GRAPH_V1", "Proof / Evidence Graph v1", "COMMAND", "ACTIVE", "PRODUCTION",
       ("Q020_SIGNAL_CONTRACT_V1",),
       "Material recommendations need traceable WHY / SHOW ME / WHAT IF evidence before higher autonomy is safe."),
''',
    "Q070/Q080 block",
)
p.write_text(s)

p = Path("test_master_execution_queue.py")
s = p.read_text()
s = replace_once(s, 'CURRENT_ITEM_ID == "Q070_SHARED_FAMILIES"', 'CURRENT_ITEM_ID == "Q080_EVIDENCE_GRAPH_V1"', "queue active test")
s = replace_once(
    s,
    '''def test_single_master_priority_continues_after_shared_families():
    ready = executable_after_current()
    assert ready == next_executable_after_current()
    assert "Q030_BR_PNCP_PCA" not in {item.id for item in ready}
    assert "Q060_CHILE_MERCADOPUBLICO" not in {item.id for item in ready}
    assert all(item.state == "QUEUED" for item in ready)
    assert ready[0].id == "Q080_EVIDENCE_GRAPH_V1"
    assert next_item_after_current().id == "Q080_EVIDENCE_GRAPH_V1"
''',
    '''def test_single_master_priority_continues_after_evidence_graph():
    ready = executable_after_current()
    assert ready == next_executable_after_current()
    assert "Q030_BR_PNCP_PCA" not in {item.id for item in ready}
    assert "Q060_CHILE_MERCADOPUBLICO" not in {item.id for item in ready}
    assert all(item.state == "QUEUED" for item in ready)
    assert ready[0].id == "Q090_COMPANY_STATE_CONTRACT"
    assert next_item_after_current().id == "Q090_COMPANY_STATE_CONTRACT"
''',
    "queue next test",
)
marker = '    assert "Q030_BR_PNCP_PCA" not in items["Q070_SHARED_FAMILIES"].dependencies\n'
s = replace_once(
    s,
    marker,
    marker + '    assert items["Q070_SHARED_FAMILIES"].state == "DONE"\n    assert items["Q080_EVIDENCE_GRAPH_V1"].state == "ACTIVE"\n',
    "queue state assertions",
)
p.write_text(s)

p = Path("test_architecture_guardrail_queue.py")
s = p.read_text()
s = replace_once(
    s,
    '    assert CURRENT_ITEM_ID == "Q070_SHARED_FAMILIES"\n',
    '    assert items["Q070_SHARED_FAMILIES"].state == "DONE"\n    assert CURRENT_ITEM_ID == "Q080_EVIDENCE_GRAPH_V1"\n',
    "architecture current item",
)
s = replace_once(
    s,
    '    assert executable_after_current()[0].id == "Q080_EVIDENCE_GRAPH_V1"\n',
    '    assert executable_after_current()[0].id == "Q090_COMPANY_STATE_CONTRACT"\n',
    "architecture next item",
)
p.write_text(s)
