import logging

import rich
from rich.console import Console
from rich.terminal_theme import TerminalTheme
from rich.theme import Theme

TERMINAL_THEME = TerminalTheme(
    (13, 21, 27),
    (220, 220, 220),
    [
        (60, 68, 77),  # black
        (175, 34, 55),  # red
        (62, 179, 131),  # green
        (255, 147, 0),  # yellow
        (38, 107, 133),  # blue
        (203, 62, 118),  # magenta
        (138, 150, 168),  # cyan
        (220, 220, 220),  # white
    ],
    [  # bright
        (81, 93, 104),  # black
        (189, 37, 61),  # red
        (83, 234, 168),  # green
        (253, 227, 129),  # yellow
        (50, 157, 204),  # blue
        (242, 74, 165),  # magenta
        (175, 2195, 219),  # cyan
        (255, 255, 255),  # white
    ],
)
theme = Theme(
    {
        "normal": "",  # No or minor danger
        "moderate": "yellow",  # Moderate danger
        "considerable": "dark_orange",  # Considerable danger
        "high": "red",  # High danger
        "veryhigh": "dim red",  # Very high danger
        "branch": "magenta",
        "wip": "bold yellow",
    }
)


def bootstrap() -> Console:
    return Console(
        theme=theme, highlighter=rich.highlighter.ReprHighlighter(), record=True
    )


def link(url: str, name: str) -> str:
    return f"[link={url}]{name}[/link]"


def get_logging_level(ctx) -> int:
    verbosity = ctx.params["verbose"]
    if ctx.params["debug"]:
        verbosity = 4
    elif ctx.params["quiet"]:
        verbosity -= ctx.params["quiet"]

    if verbosity >= 4:
        level = 1  # aka SPAM
    elif verbosity >= 3:
        level = logging.DEBUG  # 10
    elif verbosity >= 2:
        level = 25  # 25
    elif verbosity >= 1:
        level = logging.INFO  # 20
    elif verbosity == -1:
        level = logging.WARNING  # 30
    elif verbosity < -1:
        level = logging.ERROR  # 40
    else:
        level = logging.INFO

    return level
