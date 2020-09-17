#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
import sys

import click
import rich
import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

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
term = Console(theme=theme, highlighter=rich.highlighter.ReprHighlighter())

LOG = logging.getLogger(__name__)


class Config(dict):
    def __init__(self):
        super().__init__()
        self.update(self.load_config("~/.gertty.yaml"))

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
class GRI:
    def __init__(self, query=None, server=None):
        self.cfg = Config()
        self.servers = []
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
        for item in self.servers:

            for record in item.query(query=query):
                self.reviews.append(Review(record, item))

    def header(self):
        srv_list = " ".join(s.name for s in self.servers)
        return f"[dim]GRI using {len(self.servers)} servers: {srv_list}[/]"


@click.command()
@click.option("--debug", "-d", default=False, help="Debug mode", is_flag=True)
@click.option(
    "--abandon",
    "-a",
    default=False,
    help="Abandon changes (delete for drafts) when they are >90 days old "
    "and with negative score. Requires -f to perform the action.",
    is_flag=True,
)
@click.option(
    "--abandon-age",
    "-z",
    default=90,
    help="default=90, number of days for which changes are subject to abandon",
)
@click.option(
    "--force",
    "-f",
    default=False,
    help="Perform potentially destructive actions.",
    is_flag=True,
)
@click.option(
    "--incoming", "-i", default=False, help="Incoming reviews (not mine)", is_flag=True
)
@click.option(
    "--merged", "-m", default=None, type=int, help="merged in the last number of days"
)
@click.option("--user", "-u", default="self", help="Query another user than self")
@click.option(
    "--server",
    "-s",
    default=None,
    help="[0,1,2] key in list of servers, Query a single server instead of all",
)
@click.pass_context
# pylint: disable=unused-argument,too-many-arguments,too-many-locals
def main(ctx, debug, incoming, server, abandon, force, abandon_age, user, merged):
    query = None
    handler = RichHandler(show_time=False, show_path=False)
    LOG.addHandler(handler)

    LOG.warning("Called with %s", ctx.params)
    if debug:
        LOG.setLevel(level=logging.DEBUG)
    # msg =""
    # gradient = [22, 58, 94, 130, 166, 196, 124]
    # for g in gradient:
    #     msg += term.on_color(g) + "A"
    # print(msg)
    # # return

    if " " in user:
        user = f'"{user}"'

    query = ""
    if incoming:
        query += f"reviewer:{user}"
    else:
        query += f"owner:{user}"
    if merged:
        query += f" status:merged -age:{merged}d"
    else:
        query += " status:open"

    logging.info("Query used: %s", query)
    gri = GRI(query=query, server=server)
    term.print(gri.header())
    cnt = 0

    for review in sorted(gri.reviews):
        term.print(str(review))
        if ctx.params["abandon"] and review.score < 1:
            if review.age() > ctx.params["abandon_age"] and query != "incoming":
                review.abandon(dry=ctx.params["force"])
        LOG.debug(review.data)
        cnt += 1
    term.print(f"[dim]-- {cnt} changes listed[/]")


if __name__ == "__main__":

    main()  # pylint: disable=no-value-for-parameter
