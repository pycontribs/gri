import logging
import sys

import rich
from enrich.console import Console
from enrich.logging import RichHandler
from rich.console import ConsoleOptions, RenderResult
from rich.markdown import CodeBlock, Markdown
from rich.syntax import Syntax
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
    Markdown.elements["code_block"] = MyCodeBlock

    # We also initialize the logging console
    logging_console = Console(file=sys.stderr, force_terminal=1, theme=theme)

    logger = logging.getLogger()  # type: logging.Logger
    # logger.setLevel(logging.DEBUG)

    handler = RichHandler(
        console=logging_console, show_time=False, show_path=False, markup=True
    )  # type: ignore
    # logger.addHandler(handler)
    logger.handlers = [handler]
    logger.propagate = False

    return Console(
        theme=theme,
        highlighter=rich.highlighter.ReprHighlighter(),
        record=True,
        soft_wrap=True,
        redirect=True,
    )


def link(url: str, name: str) -> str:
    return f"[link={url}]{name}[/link]"


def get_logging_level(ctx) -> int:
    verbosity = ctx.params["verbose"]
    if ctx.params["debug"]:
        verbosity = 4
    elif ctx.params["quiet"]:
        verbosity -= ctx.params["quiet"]

    # our default logging level is info instead of NOTSET which may prove too verbose.
    level = logging.INFO
    if verbosity >= 4:
        level = 1  # aka SPAM
    elif verbosity == 3:
        level = logging.DEBUG  # 10
    elif verbosity == 2:
        level = 15  # 15
    elif verbosity == 1:
        level = logging.INFO  # 20
    elif verbosity == -1:
        level = logging.WARNING  # 30
    elif verbosity < -1:
        level = logging.ERROR  # 40
    return level


# pylint: disable=too-few-public-methods
class MyCodeBlock(CodeBlock):
    # pylint: disable=unused-argument
    def __rich_console__(
        self, console: rich.console.Console, options: ConsoleOptions
    ) -> RenderResult:
        code = str(self.text).rstrip()
        syntax = Syntax(code, self.lexer_name, theme=self.theme)
        yield syntax
