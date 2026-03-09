from pathlib import Path

import argparse

from commands.base import Command
from display.paper_display import (
    print_paper,
    print_neighbour_list,
    resolve_paper_id,
)
from graph.io import load_graph
from graph.metrics import compute_metrics
from core.style import rule, styled, Colour


def _enrich_attrs(node_id, attrs, metrics):
    return {
        **attrs,
        "pagerank": metrics.pagerank.get(node_id, 0.0),
        "in_degree": metrics.in_degree.get(node_id, 0),
        "out_degree": metrics.out_degree.get(node_id, 0),
    }


def run_show(graph_path, paper_id_query):
    graph = load_graph(graph_path)
    node_id = resolve_paper_id(graph, paper_id_query)
    if node_id is None:
        return

    attrs = dict(graph.nodes[node_id])
    metrics = compute_metrics(graph)
    in_neighbours = list(graph.predecessors(node_id))
    out_neighbours = list(graph.successors(node_id))

    print(rule())
    print(styled("  Paper Detail", Colour.CYAN, Colour.BOLD))
    print(rule())
    print()

    print_paper(
        node_id,
        _enrich_attrs(node_id, attrs, metrics),
        show_abstract=True,
    )
    print_neighbour_list(graph, in_neighbours, label="Cited by")
    print_neighbour_list(graph, out_neighbours, label="References")
    print(f"\n{rule()}\n")


class ShowCommand(Command):
    name = "show"
    help = "Inspect a single paper"

    def add_arguments(self, parser):
        parser.add_argument('file', help='path to graph json')
        parser.add_argument('paper_id', help='work id or bit of title')

    def run(self, args):
        run_show(Path(args.file), args.paper_id)
