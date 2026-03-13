from dataclasses import dataclass
import networkx as nx

from networkx.algorithms.link_analysis.pagerank_alg import _pagerank_python
from networkx.exception import PowerIterationFailedConvergence


@dataclass(frozen=True)
class GraphMetrics:
    pagerank: dict[str, float]
    in_degree: dict[str, int]
    out_degree: dict[str, int]


def compute_metrics(graph):
    try:
        pagerank = _pagerank_python(graph, alpha=0.85)
    except PowerIterationFailedConvergence:
        pagerank = {n: 0.0 for n in graph}

    return GraphMetrics(
        pagerank=pagerank,
        in_degree=dict(graph.in_degree()),
        out_degree=dict(graph.out_degree()),
    )
