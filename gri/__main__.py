#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import json
import logging
import netrc
import os
import re
import sys

import click
import requests
from blessings import Terminal

try:
    from urllib.parse import urlencode, urlparse
except ImportError:
    from urlparse import urlparse, urlencode  # type: ignore

import yaml
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

# Used only to force outdated Digest auth for servers not using standard auth
KNOWN_SERVERS = {
    "https://review.opendev.org/": {"auth": HTTPDigestAuth},
    "https://code.engineering.redhat.com/gerrit/": {"auth": HTTPDigestAuth},
    "verify": False,
}
term = Terminal()

LOG = logging.getLogger(__name__)


def link(url, name):
    return "\033]8;;{}\033\\{}\033]8;;\033\\".format(url, name)


# pylint: disable=too-few-public-methods
class Label:
    def __init__(self, name, data):
        self.name = name
        self.abbr = re.sub("[^A-Z]", "", name)
        self.value = 0

        if data.get("blocking", False):
            self.value += -2
        if data.get("approved", False):
            self.value += 2
        if data.get("recommended", False):
            self.value += 1
        if data.get("disliked", False):
            self.value += -1
        if data.get("rejected", False):
            self.value += -1
        if data.get("optional", False):
            self.value = 1
        for unknown in set(data.keys()) - set(
            [
                "blocking",
                "approved",
                "recommended",
                "disliked",
                "rejected",
                "value",
                "optional",
            ]
        ):
            LOG.warning("Found unknown label field %s: %s", unknown, data.get(unknown))

    def __repr__(self):
        msg = self.abbr + ":" + str(self.value)
        if self.value < 0:
            msg = term.red(msg)
        elif self.value == 0:
            msg = term.yellow(msg)
        elif self.value > 0:
            msg = term.green(msg)
        return msg


# pylint: disable=too-few-public-methods
class GerritServer:
    def __init__(self, url, name=None):
        self.url = url
        self.name = name
        parsed_uri = urlparse(url)
        if not name:
            self.name = parsed_uri.netloc
        self.auth_class = HTTPBasicAuth
        self.hostname = parsed_uri.netloc

        # name is only used as an acronym
        self.__session = requests.Session()

        if self.url in KNOWN_SERVERS:
            self.auth_class = KNOWN_SERVERS[url]["auth"]
            self.__session.verify = KNOWN_SERVERS[url].get("verify", True)

        # workaround for netrc error: OSError("Could not find .netrc: $HOME is not set")
        if "HOME" not in os.environ:
            os.environ["HOME"] = os.path.expanduser("~")

        token = netrc.netrc().authenticators(parsed_uri.netloc)

        # saving username (may be needed later)
        self.username = token[0]

        if not token:
            raise SystemError(
                f"Unable to load credentials for {url} from ~/.netrc file"
            )
        self.__session.auth = self.auth_class(token[0], token[2])

        self.__session.headers.update(
            {
                "Content-Type": "application/json;charset=UTF-8",
                "Access-Control-Allow-Origin": "*",
            }
        )

    def query(self, query=None):
        payload = [
            ("q", query),
            ("o", "LABELS"),
            ("o", "COMMIT_FOOTERS"),
        ]
        encoded = urlencode(payload, doseq=True, safe=":")
        url = rf"{self.url}a/changes/?{encoded}"
        # %20NOT%20label:Code-Review>=0,self
        return parsed(self.__session.get(url))


class CR:
    def __init__(self, data, server):
        self.data = data
        self.server = server
        self.score = 1.0

        LOG.debug(data)

        if "topic" not in data:
            self.topic = ""
        else:
            self.topic = data["topic"]

        self.is_wip = re.compile("^\\[?(WIP|DNM|POC).+$", re.IGNORECASE).match(
            self.subject
        )
        self.url = "{}#/c/{}/".format(self.server.url, self.number)

        self.labels = {}
        for label_name, label_data in data.get("labels", {}).items():
            label = Label(label_name, label_data)
            self.labels[label_name] = label
            if label.abbr == "W":
                self.score += label.value * 20
            if label.abbr == "CR":
                self.score += label.value * 10
            if label.abbr == "V":
                self.score += label.value * 5
                if label.value == 0:
                    self.score -= 100
        if self.starred:
            self.score += 10

        # We just want to keep wip changes in the same are ~0..1 score.
        if self.is_wip:
            self.score /= 100

    def __repr__(self):
        return str(self.number)

    def __getattr__(self, name):
        if name in self.data:
            return self.data[name]
        if name == "number":
            return self.data["_number"]
        return None

    def short_project(self):
        return re.search("([^/]*)$", self.project).group(0)

    def background(self):
        if self.is_wip:
            return 0
        gradient = [22, 58, 94, 130, 166, 196, 124]
        scores = [40, 15, 10, 0, -10, -20, -25]
        i = 0
        for i, score in enumerate(scores):
            if self.score > score:
                break
        return gradient[i]

    def __str__(self):

        prefix = "%s%s" % (
            "⭐" if self.starred else "  ",
            " " * (8 - len(str(self.number))),
        )

        msg = (
            term.on_color(self.background())
            + prefix
            + link(self.url, self.number)
            + term.normal
        )
        if self.is_wip:
            msg += " " + term.yellow(self.short_project())
        else:
            msg += " " + term.bright_yellow(self.short_project())

        if self.branch != "master":
            msg += term.bright_magenta(" [%s]" % self.branch)

        if self.is_wip:
            msg += term.bright_black(": %s" % (self.subject))
        else:
            msg += ": %s" % (self.subject)

        if self.topic:
            topic_url = "{}#/q/topic:{}+(status:open+OR+status:merged)".format(
                self.server.url, self.topic
            )
            msg += term.blue(" " + link(topic_url, self.topic))

        if not self.mergeable:
            msg += term.bright_red(" cannot-merge")

        for label in self.labels.values():
            if label.value:
                # we print only labels without 0 value
                msg += " %s" % label

        msg += " %s" % self.score
        return msg

    def is_reviewed(self):
        return self.data["labels"]["Code-Review"]["value"] > 1

    def __lt__(self, other):
        return self.score >= other.score

    def abandon(self, dry=True):
        # shell out here because HTTPS api to abandon can fail
        if self.draft:
            action = "delete"
        else:
            action = "abandon"

        LOG.warning("Performing %s on %s", action, self.number)
        if not dry:
            cmd = (
                f"ssh -p 29418 {self.server.username}"
                f"@{self.server.hostname} gerrit review "
                f"{self.number},1 --{action} --message too_old"
            )
            os.system(cmd)


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
                self.reviews.append(CR(record, item))

    def header(self):
        msg = "GRI using %s servers:" % len(self.servers)
        for server in self.servers:
            msg += " %s" % server.name
        return term.on_bright_black(msg)


def parsed(result):
    result.raise_for_status()

    if hasattr(result, "text") and result.text[:4] == ")]}'":
        return json.loads(result.text[5:])
    print("ERROR: %s " % (result.result_code))
    sys.exit(1)


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
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)-8s %(message)s")
    handler.setFormatter(formatter)
    LOG.addHandler(handler)
    time_now = datetime.datetime.now()

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
    print(gri.header())
    cnt = 0

    for review in sorted(gri.reviews):
        # msg = term.on_color(cr.background()) + str(cr)
        print(review)
        if ctx.params["abandon"] and review.score < 1:
            cr_last_updated = review.data["updated"]
            time_cr_updated = datetime.datetime.strptime(
                cr_last_updated[:-3], "%Y-%m-%d %H:%M:%S.%f"
            )
            cr_age = (time_now - time_cr_updated).days
            if int(cr_age) > ctx.params["abandon_age"] and query != "incoming":
                review.abandon(dry=ctx.params["force"])
        LOG.debug(review.data)
        cnt += 1
    print(term.bright_black("-- %d changes listed" % cnt))


if __name__ == "__main__":

    main()  # pylint: disable=no-value-for-parameter
