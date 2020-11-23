#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
import sys
from functools import wraps
from typing import List, Optional, Type, Union

import click
import yaml
from click_help_colors import HelpColorsGroup
from requests.exceptions import HTTPError
from rich import box
from rich.markdown import Markdown
from rich.table import Table

from gri.abc import Query, Review, Server
from gri.console import TERMINAL_THEME, bootstrap, get_logging_level
from gri.constants import RC_CONFIG_ERROR, RC_PARTIAL_RUN
from gri.gerrit import GerritServer
from gri.github import GithubServer

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse  # type: ignore

term = bootstrap()

# Respect XDG_CONFIG_HOME
CFG_FILE = "~/.config/gri/gri.yaml"
GERTTY_CFG_FILE = "~/.gertty.yaml"

LOG = logging.getLogger(__package__)


def command_line_wrapper(func):
    @wraps(func)
    def inner_func(*args, **kwargs):
        # before
        ctx = args[0]
        LOG.setLevel(get_logging_level(ctx))
        LOG.debug("Called with %s", ctx.params)

        if " " in ctx.params["user"]:
            ctx.params["user"] = f"\"{ctx.params['user']}\""

        # inner/wrapped code
        func(*args, **kwargs)
        # after
        if ctx.invoked_subcommand is None:
            LOG.debug(
                "I was invoked without subcommand, assuming implicit `owned` command"
            )
            ctx.invoke(owned)

        if ctx.params["output"]:
            term.save_html(path=ctx.params["output"], theme=TERMINAL_THEME)

        if ctx.obj.errors:
            LOG.error("Finished with %s runtime errors", ctx.obj.errors)
            sys.exit(RC_PARTIAL_RUN)

    return inner_func


class Config(dict):
    def __init__(self, file: str) -> None:
        super().__init__()
        self.update(self.load_config(file))

    def load_config(self, config_file: str) -> dict:
        self.config_file = config_file
        config_file_full = os.path.expanduser(config_file)
        if not os.path.isfile(config_file_full):
            LOG.warning(
                "%s config file missing, attempting use of %s as fallback",
                config_file_full,
                GERTTY_CFG_FILE,
            )
            config_file_full = config_file_full = os.path.expanduser(GERTTY_CFG_FILE)
        try:
            with open(config_file_full, "r") as stream:
                return dict(yaml.safe_load(stream))
        except (FileNotFoundError, yaml.YAMLError) as exc:
            LOG.error(exc)
            sys.exit(RC_CONFIG_ERROR)


# pylint: disable=too-few-public-methods,too-many-instance-attributes
class App:
    def __init__(self, ctx: click.Context) -> None:
        self.kind = ""  # keep it until we make this abc
        self.ctx = ctx
        self.cfg = Config(file=ctx.params["config"])
        self.servers: List[Server] = []
        self.user = ctx.params["user"]
        self.errors = 0  # number of errors encountered
        self.query_details: List[str] = []
        server = ctx.params["server"]
        try:
            for srv in (
                self.cfg["servers"]
                if server is None
                else [self.cfg["servers"][int(server)]]
            ):
                try:
                    # TODO(ssbarnea): make server type configurable
                    parsed_uri = urlparse(srv["url"])
                    srv_class: Union[
                        Type[GithubServer], Type[GerritServer]
                    ] = GerritServer
                    if parsed_uri.netloc == "github.com":
                        srv_class = GithubServer
                    self.servers.append(
                        srv_class(url=srv["url"], name=srv["name"], ctx=self.ctx)
                    )
                except SystemError as exc:
                    LOG.error(exc)
        except IndexError:
            LOG.error("Unable to find server %s index in server list.", server)
            sys.exit(RC_CONFIG_ERROR)
        if not self.servers:
            LOG.error("List of servers is invalid or empty.")
            sys.exit(RC_CONFIG_ERROR)

        self.reviews: List[Review] = list()
        term.print(self.header())

    def run_query(self, query: Query, kind: str) -> int:
        """Performs a query and stores result inside reviews attribute"""
        errors = 0
        self.reviews.clear()
        self.query_details = []
        for server in self.servers:

            try:
                for review in server.query(query=query, kind=kind):
                    self.reviews.append(review)
            except (HTTPError, RuntimeError) as exc:
                LOG.error(exc)
                errors += 1
            self.query_details.append(server.mk_query(query, kind=kind))

        return errors

    def header(self) -> str:
        srv_list = " ".join(s.name for s in self.servers)
        return f"[dim]GRI using {len(self.servers)} servers: {srv_list}[/]"

    def report(
        self,
        query: Query,
        title: str = "Reviews",
        max_score: int = 1,
        action: Optional[str] = None,
    ) -> None:
        """Produce a table report based on a query."""
        LOG.debug("Running report() for %s", query)
        if query:
            self.errors += self.run_query(query, kind=self.kind)
        cnt = 0

        table = Table(title=title, border_style="grey15", box=box.MINIMAL, expand=True)
        table.add_column("Review", justify="right")
        table.add_column("Age")
        table.add_column("Project/Subject")
        table.add_column("Meta")
        table.add_column("Score", justify="right")

        for review in sorted(self.reviews):
            if review.score <= max_score:
                table.add_row(*review.as_columns())
                if action:
                    LOG.warning(
                        "Performing %s on %s %s",
                        action,
                        review,
                        "(dry)" if not self.ctx.params["force"] else "",
                    )
                    if self.ctx.params["force"]:
                        getattr(review, action)()
                LOG.debug(review.data)
                cnt += 1

        # Printing empty tables makes no sense
        if cnt:
            term.print()
            term.print(table)

        term.print(f"[dim]-- {cnt} changes listed {self.query_details}[/]")

    def display_config(self) -> None:
        msg = yaml.dump(
            dict(self.cfg), default_flow_style=False, tags=False, sort_keys=False
        )
        term.print(Markdown("```yaml\n# %s\n%s\n```" % (self.cfg.config_file, msg)))


class AppIssues(App):
    def __init__(self, ctx: click.Context) -> None:
        super().__init__(ctx)
        self.kind = "issue"


class AppReviews(App):
    def __init__(self, ctx: click.Context) -> None:
        super().__init__(ctx)
        self.kind = "review"


class CustomGroup(HelpColorsGroup):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # injects common options shared across all commands using this group
        options = [
            click.core.Option(
                ["-d", "--debug"],
                default=False,
                help="Debug mode (same as -vvv)",
                is_flag=True,
            ),
            click.core.Option(
                ["--output", "-o"],
                default=None,
                help="Filename to dump the result in, currently only HTML is supported",
            ),
            click.core.Option(
                ["--force", "-f"],
                default=False,
                help="Perform potentially destructive actions.",
                is_flag=True,
            ),
            click.core.Option(
                ["-q", "--quiet"],
                count=True,
                help="Reduce verbosity level, can be specified twice.",
            ),
            click.core.Option(
                ["-v", "--verbose"], count=True, help="Increase verbosity level"
            ),
            click.core.Option(
                ["--user", "-u"], default="self", help="Query another user than self"
            ),
            click.core.Option(
                ["--config"],
                default=CFG_FILE,
                help=f"Config file to use, defaults to {CFG_FILE}",
            ),
            click.core.Option(
                ["--server", "-s"],
                default=None,
                help=(
                    "[0,1,2] key in list of servers, Query a single server "
                    "instead of all"
                ),
            ),
        ]
        self.params.extend(options)

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        """Undocumented command aliases for lazy users"""
        aliases = {
            "o": owned,
            "m": merged,
            "i": incoming,
        }
        try:
            cmd_name = aliases[cmd_name].name
        except KeyError:
            pass
        return super().get_command(ctx, cmd_name)


@click.group(
    cls=CustomGroup,
    invoke_without_command=True,
    help_headers_color="yellow",
    help_options_color="green",
    context_settings=dict(max_content_width=9999),
    chain=True,
)
@click.pass_context
@command_line_wrapper
# pylint: disable=unused-argument,too-many-arguments,too-many-locals
def cli(ctx: click.Context, **kwargs):
    """To enable shell completion, add
    eval "$(_GRI_COMPLETE=source_bash gri)" to your shell profile. Remember to
    replace bash with zsh or fish if needed.
    """
    ctx.obj = AppReviews(ctx=ctx)


@cli.resultcallback()
def process_result(result, **kwargs):  # pylint: disable=unused-argument
    output = kwargs["output"]
    if kwargs["output"]:
        term.save_html(path=output, theme=TERMINAL_THEME)
        LOG.info("Report saved to %s", output)


@cli.command()
@click.pass_context
def owned(ctx):
    """Changes originated from current user (implicit)"""
    # query = "status:open"
    # query += f" owner:{ctx.obj.user}"
    if ctx.obj.user == "self":
        title = "Own reviews"
    else:
        title = f"Reviews owned by {ctx.obj.user}"
    ctx.obj.report(query=Query("owned"), title=title)


@cli.command()
@click.pass_context
def incoming(ctx):
    """Incoming reviews"""
    ctx.obj.report(query=Query("incoming"), title=incoming.__doc__)


@cli.command()
@click.pass_context
@click.option(
    "--age",
    default=1,
    help="Number of days to look back, adds -age:NUM",
)
def merged(ctx, age):
    """Merged in the last number of days"""
    ctx.obj.report(query=Query("merged", age=age), title=f"Merged Reviews ({age}d)")


# @cli.command()
# @click.pass_context
# def custom(ctx):
#     """Custom query"""
#     query = f"cc:{ctx.obj.user} status:open"
#     ctx.obj.report(query=query, title="Custom query")


@cli.command()
@click.pass_context
def watched(ctx):
    """Watched reviews based on server side filters"""
    ctx.obj.report(query=Query("watched"), title=watched.__doc__)


@cli.command()
@click.pass_context
def draft(ctx):
    """Draft reviews or with draft comments."""
    ctx.obj.report(query=Query("draft"), title=draft.__doc__)


@cli.command()
@click.pass_context
@click.option(
    "--age",
    "-z",
    default=90,
    help="default=90, number of days for which changes are subject to abandon",
)
def abandon(ctx, age):
    """Abandon changes (delete for drafts) when they are >90 days old
    and with very low score. Requires -f to perform the action."""

    ctx.obj.report(
        query=Query("abandon", age=age),
        title=f"Reviews to abandon ({age}d)",
        max_score=1.0,
        action="abandon",
    )


@cli.command()
@click.pass_context
def config(ctx):
    """Display loaded config or a sample if configuration is missing."""
    ctx.obj.display_config()


@click.group(
    cls=CustomGroup,
    invoke_without_command=True,
    help_headers_color="yellow",
    help_options_color="green",
    context_settings=dict(max_content_width=9999),
    chain=True,
)
@click.pass_context
@command_line_wrapper
# pylint: disable=unused-argument
def cli_bugs(ctx: click.Context, **kwargs):
    """grib is gri brother that retrieves bugs instead of reviews."""
    ctx.obj = AppIssues(ctx=ctx)


if __name__ == "__main__":

    cli()  # pylint: disable=no-value-for-parameter
