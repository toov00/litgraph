import argparse
from pathlib import Path

from abc import ABC, abstractmethod

from graph.io import load_graph


class Command(ABC):
    name: str = ""
    help: str = ""

    @abstractmethod
    def add_arguments(self, parser):
        ...

    @abstractmethod
    def run(self, args):
        ...


class GraphFileCommand(Command):
    """Commands that take a graph json file and load it."""

    def add_arguments(self, parser):
        parser.add_argument('file', help='path to graph json')

    def get_graph(self, args):
        return load_graph(Path(args.file))


class OpenAlexCommand(Command):
    """Commands that talk to OpenAlex (search, explore)."""

    def add_arguments(self, parser):
        parser.add_argument(
            '--email', dest='email', default=None,
            help='email for polite pool (faster rate limit)',
        )

    def get_client(self, args):
        from api.client import OpenAlexClient
        return OpenAlexClient(email=getattr(args, 'email', None))
