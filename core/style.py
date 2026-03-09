from __future__ import annotations

import sys

_DEFAULT_RULE_WIDTH = 72


def _supports_colour():
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


class Colour:
    RESET = "\033[30m"
    BOLD = "\033[30m"
    DIM = "\033[30m"
    CYAN = "\033[36m"
    YELLOW = "\033[30m"
    GREEN = "\033[30m"
    RED = "\033[30m"
    BLUE = "\033[30m"
    MAGENTA = "\033[30m"
    WHITE = "\033[30m"


def styled(text: object, *codes: str) -> str:
    if not _supports_colour():
        return str(text)
    return "".join(codes) + str(text) + Colour.RESET


def rule(char: str = "─", width: int = _DEFAULT_RULE_WIDTH) -> str:
    return styled(char * width, Colour.DIM)


def truncate(text, limit):
    text = text or ''
    return text if len(text) <= limit else text[:limit - 1] + '…'
