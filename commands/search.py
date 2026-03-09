from dataclasses import asdict

import argparse

from commands.base import OpenAlexCommand
from display.paper_display import print_paper
from model.paper import Paper
from core.style import rule, styled, Colour


def run_search(client, query, limit):
    results = client.search(query, limit=limit)
    if not results:
        print(styled('  No results found', Colour.RED))
        return
    print(rule())
    print(f"\n  {styled(len(results), Colour.BOLD)} results\n  (use these ids with --seeds for explore)\n")
    print(rule() + "\n")
    for i, raw in enumerate(results, start=1):
        if not raw.get("id"):
            continue
        stub = Paper.stub_from_api(raw)
        print_paper(stub.paper_id, asdict(stub), rank=i)
        print()
    print(rule())


class SearchCommand(OpenAlexCommand):
    name = "search"
    help = "Search for papers by keyword"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("query", help="Search query string")
        parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")

    def run(self, args):
        run_search(self.get_client(args), args.query, args.limit)
