import json
from pathlib import Path

import networkx as nx

from core.style import styled, Colour
from graph.metrics import compute_metrics


def save_graph(graph, path):
    metrics = compute_metrics(graph)
    nodes = [
        {
            "id": node_id,
            **attrs,
            "pagerank": round(metrics.pagerank.get(node_id, 0.0), 8),
            "in_degree": metrics.in_degree.get(node_id, 0),
            "out_degree": metrics.out_degree.get(node_id, 0),
        }
        for node_id, attrs in graph.nodes(data=True)
    ]
    edges = [
        {"source": s, "target": t, **data}
        for s, t, data in graph.edges(data=True)
    ]
    path.write_text(json.dumps({'nodes': nodes, 'edges': edges}, indent=2), encoding='utf-8')
    print(styled(f'  Saved → {path}', Colour.GREEN))


def load_graph(path):
    payload = json.loads(path.read_text(encoding='utf-8'))
    graph = nx.DiGraph()
    for node in payload['nodes']:
        node_copy = dict(node)
        node_id = node_copy.pop('id')
        graph.add_node(node_id, **node_copy)
    for edge in payload['edges']:
        graph.add_edge(
            edge['source'],
            edge['target'],
            edge_type=edge.get('edge_type', ''),
        )
    return graph
