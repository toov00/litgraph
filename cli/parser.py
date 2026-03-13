import argparse

from commands import COMMANDS

_DESCRIPTION = ""


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
