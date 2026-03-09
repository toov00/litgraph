from pathlib import Path

import argparse

from api.client import OpenAlexClient
from commands.base import Command
from graph.citation_graph import build_graph
from graph.io import save_graph
from core.style import rule, styled, Colour


def run_explore(client, seeds, depth, max_nodes, output_path):
    print(rule())
    print(styled("  litgraph explore", Colour.CYAN, Colour.BOLD))
    print(rule())
    graph = build_graph(seeds, depth=depth, max_nodes=max_nodes, client=client)
    save_graph(graph, output_path)
    print(f"\n  {styled('Next steps:', Colour.BOLD)}")
    print(f"  {styled(f'litgraph top {output_path}', Colour.CYAN)}        — most influential papers")
    print(f"  {styled(f'litgraph stats {output_path}', Colour.CYAN)}      — graph statistics")
    print(f"  {styled(f'litgraph show {output_path} <id>', Colour.CYAN)}  — paper details\n")


class ExploreCommand(Command):
    name = "explore"
    help = "Crawl and save a citation graph"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--seeds", nargs="+", required=True,
            help="OpenAlex Work IDs (W<digits>), doi:<value>, or full OpenAlex URIs",
        )
        parser.add_argument(
            "--depth", type=int, default=1,
            help="BFS expansion depth (default: 1).  depth=2 is significantly slower.",
        )
        parser.add_argument(
            "--max-nodes", dest="max_nodes", type=int, default=100,
            help="Stop expanding after this many nodes (default: 100)",
        )
        parser.add_argument(
            "--output", default="graph_data.json",
            help="Output JSON file (default: graph_data.json)",
        )
        parser.add_argument(
            '--email', dest='email', default=None,
            help='email for polite pool',
        )

    def run(self, args):
        client = OpenAlexClient(email=getattr(args, "email", None))
        run_explore(
            client,
            args.seeds,
            args.depth,
            args.max_nodes,
            Path(args.output),
        )
