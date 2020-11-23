import datetime
import json
import logging
import netrc
import os
import re
from typing import Dict, List

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from gri.abc import Query, Review, Server
from gri.label import Label

try:
    from urllib.parse import urlencode, urlparse
except ImportError:
    from urlparse import urlencode, urlparse  # type: ignore


LOG = logging.getLogger(__package__)

# Used only to force outdated Digest auth for servers not using standard auth
KNOWN_SERVERS: Dict[str, Dict] = {
    "https://code.engineering.redhat.com/gerrit/": {
        "auth": HTTPDigestAuth,
        "verify": False,
    },
}
LOG = logging.getLogger(__package__)


# pylint: disable=too-few-public-methods
class GerritServer(Server):
    def __init__(self, url: str, name: str = "", ctx=None) -> None:
        super().__init__()
        self.url = url
        self.ctx = ctx
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
        netrc_file = os.path.expanduser("~/.netrc")

        try:
            token = netrc.netrc().authenticators(parsed_uri.netloc)
        except FileNotFoundError:
            token = None

        if not token:
            LOG.error(
                "Unable to load credentials for %s from %s file, "
                "likely to receive 401 errors later.",
                url,
                netrc_file,
            )
        else:
            self.__session.auth = self.auth_class(token[0], token[2])

        self.__session.headers.update(
            {
                "Content-Type": "application/json;charset=UTF-8",
                "Access-Control-Allow-Origin": "*",
            }
        )

    def query(self, query: Query, kind="review") -> List:

        # Gerrit knows only about reviews
        if kind != "review":
            return []

        gerrit_query = self.mk_query(query, kind=kind)

        payload = [
            ("q", gerrit_query),
            ("o", "LABELS"),
            ("o", "COMMIT_FOOTERS"),
        ]
        encoded = urlencode(payload, doseq=True, safe=":")
        url = rf"{self.url}a/changes/?{encoded}"
        # %20NOT%20label:Code-Review>=0,self
        return [
            ChangeRequest(data=r, server=self)
            for r in self.parsed(self.__session.get(url))
        ]

    def mk_query(self, query: Query, kind: str) -> str:
        if query.name == "owned":
            return f"status:open owner:{self.ctx.obj.user}"
        if query.name == "incoming":
            return f"reviewer:{self.ctx.obj.user} status:open"
        if query.name == "watched":
            return f"watchedby:{self.ctx.obj.user} status:open"
        if query.name == "abandon":
            return f"status:open age:{query.age}d owner:{self.ctx.obj.user}"
        if query.name == "draft":
            return "status:open owner:self has:draft OR draftby:self"
        if query.name == "merged":
            return f"status:merged -age:{query.age}d owner:{self.ctx.obj.user}"

        raise NotImplementedError(
            f"{query.name} query not implemented by {self.__class__}"
        )

    @staticmethod
    def parsed(result) -> dict:
        # Can raise HTTPError, RuntimeError
        result.raise_for_status()

        if hasattr(result, "text") and result.text[:4] == ")]}'":
            return json.loads(result.text[5:])
        raise RuntimeError(result.result_code)


class ChangeRequest(Review):  # pylint: disable=too-many-instance-attributes
    """Defines a change-request or pull-request."""

    def __init__(self, data: dict, server) -> None:
        super().__init__(data, server)
        LOG.debug(data)
        self.data = data
        self.number = data["_number"]
        self.project = data["project"]
        self.starred = data.get("starred", False)
        self.server = server

        if "topic" not in data:
            self.topic = ""
        else:
            self.topic = data["topic"]

        self.title = data["subject"]

        self.updated = datetime.datetime.strptime(
            self.data["updated"][:-3], "%Y-%m-%d %H:%M:%S.%f"
        )

        if re.compile("^\\[?(WIP|DNM|POC).+$", re.IGNORECASE).match(self.title):
            self.is_wip = True

        self.url = "{}#/c/{}/".format(self.server.url, self.number)

        # Secret ScoreRank implementation which aims to map any review on a
        # scale from 0 to 1, where 1 is alredy merged, and 0 is something that
        # willnever merge.
        #
        # We start from perfect and downgrate rating using multiplication as
        # this assures we stick between [0,1]
        self.score = 1.0
        # disabled staring as it does not effectively affect chance of merging
        # if not self.starred:
        #     self.score *= 0.9

        self.labels: Dict[str, Label] = {}

        for label_name, label_data in data.get("labels", {}).items():
            label = Label(label_name, label_data)
            self.labels[label_name] = label

            if label.abbr == "V" and label.value < 1:
                self.score *= 0.8 if label.value == 0 else 0.6
            if label.abbr == "W" and label.value < 1:
                self.score *= 0.95 if label.value == 0 else 0.5
            if label.abbr == "CR" and label.value < 1:
                self.score *= 0.8 if label.value == 0 else 0.3

        # penalty for reviews over 7 days old
        if self.age() > 7:
            self.score *= 1 - (min(365, self.age()) / 365)

        # We just want to keep wip changes in the same are ~0..1 score.
        if self.is_wip:
            self.score *= 0.05

    def __getattr__(self, name):
        if name in self.data:
            return self.data[name]
        if name == "number":
            return self.data["_number"]
        return None

    def short_project(self) -> str:
        match = re.search("([^/]*)$", self.project)
        if match:
            return match.group(0)
        return self.project

    def colorize(self, text: str) -> str:
        style = ""
        if self.status == "NEW" and not self.mergeable:
            style = "dim red"
        elif self.is_wip:
            style = "wip"
        if style:
            return f"[{style}]{text}[/]"
        return text

    # def as_columns(self) -> list:
    #     """Return review info as columns with rich text."""

    #     result = []

    #     # avoid use of emoji due to:
    #     # https://github.com/willmcgugan/rich/issues/148
    #     star = "[bright_yellow]★[/] " if self.starred else ""

    #     result.append(f"{star}{self.colorize(link(self.url, self.number))}")

    #     result.append(f"[dim]{self.age():3}[/]" if self.age() else "")

    #     msg = f"[{ 'wip' if self.is_wip else 'normal' }]{self.short_project()}[/]"

    #     if self.branch != "master":
    #         msg += f" [branch][{self.branch}][/]"

    #     msg += "[dim]: %s[/]" % (self.title)

    #     if self.topic:
    #         topic_url = "{}#/q/topic:{}+(status:open+OR+status:merged)".format(
    #             self.server.url, self.topic
    #         )
    #         msg += f" {link(topic_url, self.topic)}"

    #     if self.status == "NEW" and not self.mergeable:
    #         msg += " [veryhigh]cannot-merge[/]"
    #     result.append(msg)

    #     msg = ""
    #     for label in self.labels.values():
    #         if label.value:
    #             # we print only labels without 0 value
    #             msg += " %s" % label

    #     result.extend([msg.strip(), f" [dim]{self.score*100:.0f}%[/]"])

    #     return result

    def is_reviewed(self) -> bool:
        return self.data["labels"]["Code-Review"]["value"] > 1

    def __lt__(self, other) -> bool:
        return self.score >= other.score

    def abandon(self, dry=True) -> None:
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

    @property
    def status(self):
        return self.data["status"]

    @property
    def is_mergeable(self):
        return self.status == "NEW" and not self.mergeable
