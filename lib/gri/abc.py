import datetime
from abc import ABC
from dataclasses import dataclass
from typing import Dict, Iterator, List

from gri.console import link
from gri.label import Label


@dataclass
class Query:
    name: str
    age: int = 0


class Server(ABC):  # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.name = "Unknown"

    def query(self, query: Query, kind: str = "review") -> List:
        raise NotImplementedError()

    def mk_query(self, query: Query, kind: str) -> str:
        raise NotImplementedError()


class Review:  # pylint: disable=too-many-instance-attributes
    """Defines a change-request or pull-request."""

    def __init__(self, data: dict, server) -> None:
        self.score = 1.0
        self.data = data
        self.title: str = ""
        self.starred = False
        self.url = ""
        self.number = "0"
        self.is_wip: bool = False
        self.project = ""
        self.branch = "master"
        self.topic = ""
        self.labels: Dict[str, Label] = {}
        self.server = server

    def age(self) -> int:
        """Return how many days passed since last update was made."""
        time_now = datetime.datetime.now()
        return int((time_now - self.updated).days)

    def __repr__(self) -> str:
        return str(self.number)

    def __getattr__(self, name):
        if name in self.data:
            return self.data[name]
        raise AttributeError(f"{name} not found in {self.data}")
        # if name == "number":
        #     return self.data["_number"]
        # return None

    def short_project(self) -> str:
        return self.project

    def colorize(self, text: str) -> str:  # pylint: disable=no-self-use
        return text

    def as_columns(self) -> list:
        """Return review info as columns with rich text."""
        # return [self.title]

        result = []

        # avoid use of emoji due to:
        # https://github.com/willmcgugan/rich/issues/148
        star = "[bright_yellow]★[/] " if self.starred else ""

        result.append(f"{star}{self.colorize(link(self.url, self.number))}")

        result.append(f"[dim]{self.age():3}[/]" if self.age() else "")

        msg = f"[{ 'wip' if self.is_wip else 'normal' }]{self.short_project()}[/]"

        if self.branch != "master":
            msg += f" [branch][{self.branch}][/]"

        # description/detail column
        msg += "[dim]: %s[/]" % (self.title)

        if self.topic:
            topic_url = "{}#/q/topic:{}+(status:open+OR+status:merged)".format(
                self.server.url, self.topic
            )
            msg += f" {link(topic_url, self.topic)}"

        if self.status == "NEW" and not self.mergeable:
            msg += " [veryhigh]cannot-merge[/]"

        for label in self._get_labels(meta=False):
            msg += f" [blue]{label.name}[/]"

        result.append(msg)

        # meta column, used to display short status symbols
        msg = ""
        for label in self._get_labels(meta=True):
            # we do not display labels with no value
            if label.value:
                msg += " %s" % label

        result.extend([msg.strip(), f" [dim]{self.score*100:.0f}%[/]"])

        return result

    def _get_labels(self, meta=False) -> Iterator[Label]:
        """Return labels that are part of meta group or opposite."""
        for label in self.labels.values():
            if label.is_meta() == meta:
                yield label

    @property
    def is_mergeable(self):
        raise NotImplementedError()

    def is_reviewed(self) -> bool:
        pass

    def __lt__(self, other) -> bool:
        pass

    def abandon(self, dry=True) -> None:
        # shell out here because HTTPS api to abandon can fail
        pass
