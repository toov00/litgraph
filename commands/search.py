from dataclasses import asdict

import argparse

from api.client import OpenAlexClient
from commands.base import Command
from display.paper_display import print_paper
from model.paper import Paper
from core.style import rule, styled, Colour


def run_search(client: OpenAlexClient, query: str, limit: int) -> None:
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


class SearchCommand(Command):
    name = "search"
    help = "Search for papers by keyword"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("query", help="Search query string")
        parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
        parser.add_argument(
            '--email', dest='email', default=None,
            help='email for polite pool (faster rate limit)',
        )

    def run(self, args):
        client = OpenAlexClient(email=getattr(args, "email", None))
        run_search(client, args.query, args.limit)
