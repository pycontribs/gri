#!/usr/bin/env python
from blessings import Terminal
import json
import logging
import netrc
import os
import re
import requests
import sys

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
import yaml
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

# Used only to force outdated Digest auth for servers not using standard auth
KNOWN_SERVERS = {
    "https://review.opendev.org/": {"auth": HTTPDigestAuth},
    "https://code.engineering.redhat.com/gerrit/": {"auth": HTTPDigestAuth},
}
term = Terminal()


def link(url, name):
    return "\033]8;;{}\033\\{:>6}\033]8;;\033\\".format(url, name)


class Label(object):
    def __init__(self, name, data):
        self.name = name
        self.abbr = re.sub("[^A-Z]", "", name)
        self.value = data.get("disliked", 0)
        if data.get("blocking", False):
            self.value = -2
        if data.get("approved", False):
            self.value = 2
        if data.get("recommended", False):
            self.value = 1
        if data.get("disliked", False):
            self.value = -1
        if data.get("rejected", False):
            self.value = -1
        unknown = set(data.keys()) - set(
            ["blocking", "approved", "recommended", "disliked", "rejected", "value"]
        )
        if unknown:
            logging.error("Found unknown label field %s" % unknown)

    def __repr__(self):
        msg = self.abbr + ":" + str(self.value)
        if self.value < 0:
            msg = term.red(msg)
        elif self.value == 0:
            msg = term.yellow(msg)
        elif self.value > 0:
            msg = term.green(msg)
        return msg


class GerritServer(object):
    def __init__(self, url, name=None):
        self.url = url
        self.name = name
        parsed_uri = urlparse(url)
        if not name:
            self.name = parsed_uri.netloc
        self.auth_class = HTTPBasicAuth
        if self.url in KNOWN_SERVERS:
            self.auth_class = KNOWN_SERVERS[url]["auth"]

        # name is only used as an acronym
        self.__session = requests.Session()
        # workaround for netrc error: OSError("Could not find .netrc: $HOME is not set")
        if "HOME" not in os.environ:
            os.environ["HOME"] = os.path.expanduser("~")

        token = netrc.netrc().authenticators(parsed_uri.netloc)
        if not token:
            raise SystemError(
                "Unable to load credentials for %s from ~/.netrc file, add them dear human!", url
            )
        self.__session.auth = self.auth_class(token[0], token[2])

        self.__session.headers.update(
            {"Content-Type": "application/json;charset=UTF-8", "Access-Control-Allow-Origin": "*"}
        )

    def my_changes(self):
        query = "%sa/changes/?q=owner:self%%20status:open&o=LABELS&o=COMMIT_FOOTERS" % self.url
        return parsed(self.__session.get(query))


class CR(object):
    def __init__(self, data, server):
        super().__init__()
        self.data = data
        self.server = server
        if "topic" not in data:
            self.topic = ""
        else:
            self.topic = data["topic"]

        self.is_wip = re.compile("^\\[?(WIP|DNM|POC).+$", re.IGNORECASE).match(self.subject)
        self.url = "{}#/c/{}/".format(self.server.url, self.number)

        self.labels = {}
        for label_name, label_data in data.get("labels", {}).items():
            self.labels[label_name] = Label(label_name, label_data)

    def __repr__(self):
        return str(self.number)

    def __getattr__(self, name):
        if name in self.data:
            return self.data[name]
        elif name == "number":
            return self.data["_number"]

    def __str__(self):
        msg = link(self.url, self.number)
        msg += ": %s" % (self.subject)
        if self.topic:
            topic_url = "{}/#/q/topic:{}+(status:open+OR+status:merged)".format(
                self.server.url, self.topic
            )
            msg += term.blue + " " + link(topic_url, self.topic) + term.normal
        if not self.mergeable:
            msg += term.yellow + " not-mergeable" + term.normal
        if self.is_wip:
            msg = term.bright_black(msg)
        for l in self.labels.values():
            if l.value:
                # we print only labels without 0 value
                msg += " %s" % l
        return msg

    def is_reviewed(self):
        return self.data["labels"]["Code-Review"]["value"] > 1


class Config(dict):
    def __init__(self):
        self.update(self.load_config("~/.gertty.yaml"))

    def load_config(self, config_file):
        config_file = os.path.expanduser(config_file)
        with open(config_file, "r") as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                logging.error(exc)
                sys.exit(2)


class GRI(object):
    def __init__(self):
        self.cfg = Config()
        self.servers = []
        for s in self.cfg["servers"]:
            try:
                self.servers.append(GerritServer(url=s["url"], name=s["name"]))
            except SystemError as e:
                logging.error(e)
        if not self.servers:
            sys.exit(1)

    def header(self):
        msg = "GRI using %s servers:" % len(self.servers)
        for s in self.servers:
            msg += " %s" % s.name
        return term.on_bright_black(msg)


def parsed(result):
    result.raise_for_status()

    if hasattr(result, "text") and result.text[:4] == ")]}'":
        return json.loads(result.text[5:])
    else:
        print("ERROR: %s " % (result.result_code))
        sys.exit(1)


def main():
    gri = GRI()
    print(gri.header())
    cnt = 0
    for server in gri.servers:

        for r in server.my_changes():
            cr = CR(r, server)
            print(cr)
            cnt += 1
    print(term.bright_black("-- %d changes listed" % cnt))


if __name__ == "__main__":
    main()
