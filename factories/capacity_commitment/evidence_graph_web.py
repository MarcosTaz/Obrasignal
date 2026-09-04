from __future__ import annotations

from flask import g, jsonify

from .evidence_graph import build_case_evidence_graph


def _node_payload(node):
    return {
        "node_id": node.node_id,
        "node_type": node.node_type,
        "attributes": dict(node.attributes),
    }


def _edge_payload(edge):
    return {
        "from_node": edge.from_node,
        "to_node": edge.to_node,
        "relation": edge.relation,
    }


def register_evidence_graph_routes(app, repository):
    @app.route("/api/capacity/cases/<case_id>/evidence-graph", methods=["GET"])
    def evidence_graph(case_id):
        graph = build_case_evidence_graph(
            repository,
            tenant_id=g.capacity_tenant_id,
            case_id=case_id,
        )
        response = jsonify(
            {
                "case_id": graph.case_id,
                "fact_provenance_complete": graph.fact_provenance_complete,
                "nodes": [_node_payload(item) for item in graph.nodes],
                "edges": [_edge_payload(item) for item in graph.edges],
                "truth_rule": "graph traces persisted evidence and workflow facts; engine result is not payment proof",
            }
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    return app
