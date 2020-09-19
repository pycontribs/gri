import json
import logging
import netrc
import os
import sys

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from requests.exceptions import HTTPError

try:
    from urllib.parse import urlencode, urlparse
except ImportError:
    from urlparse import urlencode, urlparse  # type: ignore

# Used only to force outdated Digest auth for servers not using standard auth
KNOWN_SERVERS = {
    "https://review.opendev.org/": {"auth": HTTPDigestAuth},
    "https://code.engineering.redhat.com/gerrit/": {"auth": HTTPDigestAuth},
    "verify": False,
}
LOG = logging.getLogger(__package__)


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
        try:
            result.raise_for_status()
        except HTTPError as exc:
            LOG.error(exc)
            sys.exit(2)

        if hasattr(result, "text") and result.text[:4] == ")]}'":
            return json.loads(result.text[5:])
        raise RuntimeError(result.result_code)
