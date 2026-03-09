import argparse

from commands import COMMANDS

_DESCRIPTION = """EXAMPLES:
  Search for seed papers:
    litgraph search "<some keywords>" --limit 10

  Build a graph from seeds (OpenAlex Work IDs or DOIs):
    litgraph explore --seeds W2741809807
    litgraph explore --seeds W2741809807 doi:10.1145/3320269.3384724 \\
                     --depth 1 --max-nodes 80 --output my_graph.json

  Inspect the graph:
    litgraph stats  my_graph.json
    litgraph top    my_graph.json --by pagerank --n 20
    litgraph top    my_graph.json --by citations
    litgraph show   my_graph.json W2741809807
    litgraph show   my_graph.json "water treatment"  # title fragment

  Speed up with the OpenAlex polite pool (no signup, just your email):
    litgraph search "<some keywords>" --email you@university.edu
    litgraph explore --seeds W2741809807 --email you@university.edu
"""


def build_subparser(sub):
    for cmd_cls in COMMANDS:
        cmd = cmd_cls()
        parser = sub.add_parser(cmd.name, help=cmd.help)
        cmd.add_arguments(parser)
        parser.set_defaults(func=cmd.run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="litgraph",
        description="Map citation networks from OpenAlex.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_DESCRIPTION,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    build_subparser(sub)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
