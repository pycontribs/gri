#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
import sys

import click
import rich
import yaml
from click_help_colors import HelpColorsGroup
from rich import box
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
from rich.theme import Theme

from gri.console import TERMINAL_THEME
from gri.gerrit import GerritServer
from gri.review import Review

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
term = Console(theme=theme, highlighter=rich.highlighter.ReprHighlighter(), record=True)
CFG_FILE = "~/.gertty.yaml"

LOG = logging.getLogger(__package__)


class Config(dict):
    def __init__(self, file):
        super().__init__()
        self.update(self.load_config(file))

    @staticmethod
    def load_config(config_file):
        config_file = os.path.expanduser(config_file)
        with open(config_file, "r") as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                LOG.error(exc)
                sys.exit(2)


# pylint: disable=too-few-public-methods
class App:
    def __init__(self, ctx):
        self.ctx = ctx
        self.cfg = Config(file=ctx.params["config"])
        self.servers = []
        self.user = ctx.params["user"]
        server = ctx.params["server"]
        for srv in (
            self.cfg["servers"]
            if server is None
            else [self.cfg["servers"][int(server)]]
        ):
            try:
                self.servers.append(GerritServer(url=srv["url"], name=srv["name"]))
            except SystemError as exc:
                LOG.error(exc)
        if not self.servers:
            sys.exit(1)

        self.reviews = list()
        term.print(self.header())

    def run_query(self, query):
        """Performs a query and stores result inside reviews attribute"""
        self.reviews = list()
        for item in self.servers:

            for record in item.query(query=query):
                self.reviews.append(Review(record, item))

    def header(self):
        srv_list = " ".join(s.name for s in self.servers)
        return f"[dim]GRI using {len(self.servers)} servers: {srv_list}[/]"

    def report(self, query=None, title="Reviews", max_score=1, action=None):
        """Produce a table report based on a query."""
        if query:
            self.run_query(query)

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

        extra = f" from: [cyan]{query}[/]" if query else ""
        term.print(f"[dim]-- {cnt} changes listed{extra}[/]")


class CustomGroup(HelpColorsGroup):
    def get_command(self, ctx, cmd_name):
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
@click.option("--user", "-u", default="self", help="Query another user than self")
@click.option(
    "--config", default=CFG_FILE, help=f"Config file to use, defaults to {CFG_FILE}"
)
@click.option(
    "--server",
    "-s",
    default=None,
    help="[0,1,2] key in list of servers, Query a single server instead of all",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Filename to dump the result in, currently only HTML is supported",
)
@click.option(
    "--force",
    "-f",
    default=False,
    help="Perform potentially destructive actions.",
    is_flag=True,
)
@click.option("--debug", "-d", default=False, help="Debug mode", is_flag=True)
@click.pass_context
# pylint: disable=unused-argument,too-many-arguments,too-many-locals
def cli(ctx, **kwargs):

    handler = RichHandler(show_time=False, show_path=False)
    LOG.addHandler(handler)

    LOG.warning("Called with %s", ctx.params)
    if ctx.params["debug"]:
        LOG.setLevel(level=logging.DEBUG)

    if " " in ctx.params["user"]:
        ctx.params["user"] = f"\"{ctx.params['user']}\""

    # import pdb
    # pdb.set_trace()
    ctx.obj = App(ctx=ctx)

    if ctx.invoked_subcommand is None:
        LOG.info("I was invoked without subcommand, assuming implicit `owned` command")
        ctx.invoke(owned)

    if ctx.params["output"]:
        term.save_html(path=ctx.params["output"], theme=TERMINAL_THEME)


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
    query = "status:open"
    query += f" owner:{ctx.obj.user}"
    if ctx.obj.user == "self":
        title = "Own reviews"
    else:
        title = f"Reviews owned by {ctx.obj.user}"
    ctx.obj.report(query=query, title=title)


@cli.command()
@click.pass_context
def incoming(ctx):
    """Incoming reviews"""
    query = f"reviewer:{ctx.obj.user} status:open"
    ctx.obj.report(query=query, title=incoming.__doc__)


@cli.command()
@click.pass_context
@click.option(
    "--age",
    default=1,
    help="Number of days to look back, adds -age:NUM",
)
def merged(ctx, age):
    """Merged in the last number of days"""
    query = f"status:merged -age:{age}d owner:{ctx.obj.user}"
    ctx.obj.report(query=query, title=f"Merged Reviews ({age}d)")


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
    query = f"watchedby:{ctx.obj.user} status:open"
    ctx.obj.report(query=query, title=watched.__doc__)


@cli.command()
@click.pass_context
def draft(ctx):
    """Draft reviews or with draft comments."""
    query = "status:open owner:self has:draft OR draftby:self"
    ctx.obj.report(query=query, title=draft.__doc__)


@cli.command()
@click.pass_context
@click.option(
    "--age",
    "-z",
    default=90,
    help="default=90, number of days for which changes are subject to abandon",
)
def abandon(ctx, age):
    """Abandon changes (delete for drafts) when they are >90 days old "
    "and with very low score. Requires -f to perform the action."""
    query = f"status:open age:{age}d owner:{ctx.obj.user}"

    ctx.obj.report(
        query=query,
        title=f"Reviews to abandon ({age}d)",
        max_score=0.1,
        action="abandon",
    )


if __name__ == "__main__":

    cli()  # pylint: disable=no-value-for-parameter
