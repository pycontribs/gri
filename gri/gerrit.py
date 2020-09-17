import os
import netrc
import requests
import sys
import json
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

try:
    from urllib.parse import urlencode, urlparse
except ImportError:
    from urlparse import urlparse, urlencode  # type: ignore

# Used only to force outdated Digest auth for servers not using standard auth
KNOWN_SERVERS = {
    "https://review.opendev.org/": {"auth": HTTPDigestAuth},
    "https://code.engineering.redhat.com/gerrit/": {"auth": HTTPDigestAuth},
    "verify": False,
}


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
        return self.parsed(self.__session.get(url))

    @staticmethod
    def parsed(result):
        result.raise_for_status()

        if hasattr(result, "text") and result.text[:4] == ")]}'":
            return json.loads(result.text[5:])
        raise RuntimeError(result.result_code)
