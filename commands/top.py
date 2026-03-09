import argparse
import networkx as nx

from commands.base import GraphFileCommand
from display.paper_display import print_paper
from graph.metrics import compute_metrics
from core.style import rule, styled, Colour


def _sort_key_fns():
    return {
        "pagerank": (lambda m, nid, data: m.pagerank.get(nid, 0.0), "by PageRank"),
        "citations": (lambda m, nid, data: data.get("citation_count", 0), "by citation count"),
        "year": (lambda m, nid, data: data.get("year") or 0, "by year (newest first)"),
    }


def _enrich_node_attrs(node_id, attrs, metrics):
    return {
        **attrs,
        "pagerank": metrics.pagerank.get(node_id, 0.0),
        "in_degree": metrics.in_degree.get(node_id, 0),
        "out_degree": metrics.out_degree.get(node_id, 0),
    }


def run_top(graph, by, n):
    metrics = compute_metrics(graph)
    nodes = list(graph.nodes(data=True))
    sort_map = _sort_key_fns()
    key_fn, label = sort_map[by]
    ranked = sorted(
        nodes,
        key=lambda x: key_fn(metrics, x[0], x[1]),
        reverse=True,
    )
    n = min(n, len(ranked))

    print(rule())
    print(styled(f"  Top {n} papers {label}", Colour.CYAN, Colour.BOLD))
    print(rule())
    print()

    for rank, (node_id, attrs) in enumerate(ranked[:n], start=1):
        enriched = _enrich_node_attrs(node_id, attrs, metrics)
        print_paper(node_id, enriched, rank=rank)
        print()
    print(rule())


class TopCommand(GraphFileCommand):
    name = "top"
    help = "List most influential papers"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--by", choices=["pagerank", "citations", "year"], default="pagerank",
            help="Sort criterion (default: pagerank)",
        )
        parser.add_argument('--n', type=int, default=15, help='how many to show (default 15)')

    def run(self, args):
        run_top(self.get_graph(args), args.by, args.n)
