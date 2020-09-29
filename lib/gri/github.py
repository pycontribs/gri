import datetime
import logging
import os
from typing import Dict, List

import github

from gri.abc import Review, Server
from gri.review import Label

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse  # type: ignore

LOG = logging.getLogger(__package__)


class GithubServer(Server):
    def __init__(self, url: str, name: str = "", ctx=None) -> None:
        super().__init__()
        self.name = name
        self.url = url
        self.ctx = ctx
        token = os.environ.get("HOMEBREW_GITHUB_API_TOKEN")
        self.github = github.Github(login_or_token=token)

    def query(self, query=None) -> List:
        reviews = []
        limit = 5
        results = self.github.search_issues(self.mk_query(query))
        for _, item in zip(range(limit), results):
            review = PullRequest(data=item.raw_data, server=self)
            reviews.append(review)
        # mine = [x for x in self.github.search_issues("author:@me")]
        # print(mine)
        return reviews

    def mk_query(self, query: str) -> str:  # pylint: disable=no-self-use
        """Return query string based on """
        if query == "owned":
            return "is:pr is:open author:@me"
        if query == "incoming":
            return "is:pr is:open involves:@me -author:@me"
        raise NotImplementedError(f"Unable to build query for {query}")


class PullRequest(Review):  # pylint: disable=too-many-instance-attributes
    def __init__(self, data: dict, server) -> None:
        super().__init__(data, server)
        self.title = data["title"]
        self.url = data["html_url"]
        self.number = data["number"]
        self.data = data
        # LOG.error(data)
        self.server = server
        self.updated = datetime.datetime.strptime(
            self.data["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
        )
        self.state = data["state"]
        path = urlparse(self.url).path.split("/")
        self.org = path[1]
        self.project = path[2]
        if data.get("draft", False):
            self.is_wip = True

        self.labels: Dict[str, Label] = {}
        if isinstance(data.get("labels", {}), list):  # github
            for label_data in data.get("labels", []):
                label = Label(label_data["name"], label_data)
                self.labels[label_data["name"]] = label

        # TODO add labels
        # print(_)
        # locked
        # assignee
        # closed_at
        # closed_by

    @property
    def status(self):
        return self.data["state"]

    @property
    def is_mergeable(self):
        return self.state == "open"
