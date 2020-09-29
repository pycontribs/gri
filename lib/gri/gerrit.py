import json
import logging
import netrc
import os
from typing import Dict, List

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from gri.abc import Query, Server
from gri.review import ChangeRequest

try:
    from urllib.parse import urlencode, urlparse
except ImportError:
    from urlparse import urlencode, urlparse  # type: ignore

# Used only to force outdated Digest auth for servers not using standard auth
KNOWN_SERVERS: Dict[str, Dict] = {
    "https://review.opendev.org/": {"auth": HTTPDigestAuth},
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

    def query(self, query: Query) -> List:

        gerrit_query = self.mk_query(query)

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

    def mk_query(self, query: Query) -> str:
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
