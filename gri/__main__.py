#!/usr/bin/env python
import json
import logging
import netrc
import re
import sys

import requests
from blessings import Terminal

# from pygments import formatters, highlight, lexers
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

KNOWN_SERVERS = {
    "review.rdoproject.org": {"prefix": "/r", "auth": HTTPBasicAuth, "name": "rdo"},
    "review.opendev.org": {"prefix": "", "auth": HTTPDigestAuth, "name": "roo"},
}

term = Terminal()


def link(url, name):
    return "\033]8;;{}\033\\{:>6}\033]8;;\033\\".format(url, name)


class Label(object):
    def __init__(self, name, data):
        self.name = name
        self.abbr = re.sub("[^A-Z]", "", name)
        self.value = 0
        # print(name, data)
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
        # for x in data.keys():
        #     if hasattr(x, 'value'):
        #         self.value += x['value']
        #     # else:
        #     #     print(term.magenta_on_white(str(x)))

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
    def __init__(self, fqdn):
        self.fqdn = fqdn
        self.url = "https://" + fqdn
        self.auth_class = HTTPBasicAuth
        if self.fqdn in KNOWN_SERVERS:
            self.url += KNOWN_SERVERS[fqdn]["prefix"]
            self.name = KNOWN_SERVERS[fqdn]["name"]
            self.auth_class = KNOWN_SERVERS[fqdn]["auth"]
        else:
            self.name = fqdn
        # name is only used as an acronym
        self.__session = requests.Session()
        token = netrc.netrc().authenticators(fqdn)
        if not token:
            logging.error(
                "Unable to load credentials for %s from ~/.netrc file, add them dear human!", fqdn
            )
            sys.exit(1)
        self.__session.auth = self.auth_class(token[0], token[2])

        self.__session.headers.update(
            {"Content-Type": "application/json;charset=UTF-8", "Access-Control-Allow-Origin": "*"}
        )

    def my_changes(self):
        query = "%s/a/changes/?q=owner:self%%20status:open&o=LABELS&o=COMMIT_FOOTERS" % self.url
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

        self.is_wip = re.compile("^\[?(WIP|DNM|POC).+$", re.IGNORECASE).match(self.subject)
        self.url = "{}/#/c/{}/".format(self.server.url, self.number)

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
        # workflow = self.labels.get('Workflow', {})
        # # print(workflow)
        # if 'approved' in workflow:
        #     msg += term.green(' approved')
        # elif 'rejected' in workflow:
        #     msg += term.red(' rejected')
        # elif workflow:
        #     msg += term.pink_on_white(str(workflow))
        if self.is_wip:
            msg = term.bright_black(msg)
        for l in self.labels.values():
            if l.value:
                # we print only labels without 0 value
                msg += " %s" % l
        return msg

    def is_reviewed(self):
        return self.data["labels"]["Code-Review"]["value"] > 1


def parsed(result):
    result.raise_for_status()

    if hasattr(result, "text") and result.text[:4] == ")]}'":
        return json.loads(result.text[5:])
    else:
        print("ERROR: %s " % (result.result_code))
        sys.exit(1)


def main():

    for fqdn in ["review.rdoproject.org", "review.opendev.org", "review.gerrithub.io"]:
        server = GerritServer(fqdn)

        for r in server.my_changes():
            # change_id = r['change_id']
            # u = url + '/changes/%s/revisions/current/commit' % r['id']
            # c = parsed(s.get(u))
            # r['subject'] = c['subject']
            # r['message'] = c['message']
            cr = CR(r, server)
            # print(x.status_code, x.text, u)

            # formatted_json = json.dumps(r, sort_keys=True, indent=2)
            # print(formatted_json)

            # colorful_json = highlight(
            #     formatted_json, 'UTF-8',
            #     lexers.JsonLexer(),
            #     formatters.TerminalFormatter())
            # print(colorful_json)
            # if 'topic' not in r:
            #     r['topic'] = ''
            # msg = link("https://review.opendev.org/r/%s" % r['_number'], r['_number']) + \
            #         ": %s (%s)" % (r['subject'], r['topic'])
            # if r['mergeable']:
            #     msg += term.green + ' mergeable' + term.normal
            # msg += "X" if r['submittable'] else ""
            # msg += r['status']
            # print(msg, c['message'])
            print(cr)

        # print(term.bold_underline_green_on_yellow + 'Woo' + term.normal)


if __name__ == "__main__":
    main()
