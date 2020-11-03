import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List

import github

from gri.abc import Query, Review, Server
from gri.label import Label

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

    def query(self, query: Query, kind="review") -> List:
        LOG.debug("Called query=%s and kind=%s", query, kind)
        reviews = []
        limit = 50
        results = self.github.search_issues(self.mk_query(query, kind=kind))
        for _, item in zip(range(limit), results):
            review = PullRequest(data=item.raw_data, server=self)
            reviews.append(review)
        # mine = [x for x in self.github.search_issues("author:@me")]
        # print(mine)
        return reviews

    def mk_query(
        self, query: Query, kind: str = "review"
    ) -> str:  # pylint: disable=no-self-use
        """Return query string based on """
        # https://docs.github.com/en/free-pro-team@latest/github/searching-for-information-on-github/searching-issues-and-pull-requests
        kind = "is:pr" if kind == "review" else "is:issue"

        # we do not want results from archived repos as nobody can change them
        kind += " archived:no"

        if query.name == "owned":
            return f"{kind} is:open author:@me"
        if query.name == "incoming":
            return f"{kind} is:open involves:@me -author:@me"
        if query.name == "watched":
            return f"{kind} is:open involves:@me -author:@me"
        if query.name == "abandon":
            day = (datetime.now() - timedelta(days=query.age)).date().isoformat()
            return f"{kind} is:open author:@me updated:<={day}"
        if query.name == "draft":
            return f"{kind} draft:true is:open author:@me"
        if query.name == "merged":
            day = (datetime.now() - timedelta(days=query.age)).date().isoformat()
            return f"{kind} is:merged author:@me updated:>={day}"

        raise NotImplementedError(f"Unable to build query for {query.name}")


class PullRequest(Review):  # pylint: disable=too-many-instance-attributes
    def __init__(self, data: dict, server) -> None:
        super().__init__(data, server)
        self.title = data["title"]
        self.url = data["html_url"]
        self.number = data["number"]
        self.data = data
        # LOG.error(data)
        self.server = server
        self.updated = datetime.strptime(self.data["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
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
