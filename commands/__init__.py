from commands.base import Command
from commands.explore import ExploreCommand
from commands.show import ShowCommand
from commands.stats import StatsCommand
from commands.search import SearchCommand
from commands.top import TopCommand

COMMANDS: tuple[type[Command], ...] = (
    SearchCommand,
    ExploreCommand,
    StatsCommand,
    TopCommand,
    ShowCommand,
)

__all__ = [
    "Command",
    "COMMANDS",
    "SearchCommand",
    "ExploreCommand",
    "StatsCommand",
    "TopCommand",
    "ShowCommand",
]
