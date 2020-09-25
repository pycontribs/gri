# gri : Git Reduced Interface

`gri` is a CLI tool that **lists git reviews** from multiple servers
in a way that makes easier to to identify which one need you attention.

Currently supported backends are Gerrit and GitHub but it should be easy to
add others if needed.

![screenshot](https://sbarnea.com/ss/Screen-Shot-2020-09-18-10-41-05.06.png)

## Features

* combines results from multiple Gerrit or GitHub servers
* uses terminal clickable links to make it easy to access these reviews
* displays important metadata related to reviews in a compressed format
* reviews are sorted based on probablility of getting merged
* allows user to abandon very old reviews
* can be used to query:
  * already merged reviews
  * incoming reviews (where you are a reviewer)
  * reviewes created by other users than yourself
* produce HTML reports

## Installing

```bash
pip install gri
```

## Usage

You can just run `gri`, or `python -m gri` in order to get a list of your
current reviews, aslo known as outgoing reviews.

GRI uses a simple config file [`~/.config/gri/gri.yaml`][1] but when the file
is missing, it will try to load servers from [`~/.gertty.yaml`][2] in case you
have one.

```console
$ gri --help
Usage: gri [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...

Options:
  -a, --abandon              Abandon changes (delete for drafts) when they are
                              >90 days old and with negative score. Requires -f
                             to perform the action.
  -z, --abandon-age INTEGER  default=90, number of days for which changes are
                             subject to abandon
  -u, --user TEXT            Query another user than self
  -s, --server TEXT          [0,1,2] key in list of servers, Query a single
                             server instead of all
  -o, --output TEXT          Filename to dump the result in, currently only
                             HTML is supported
  -f, --force                Perform potentially destructive actions.
  -d, --debug                Debug mode
  --help                     Show this message and exit.

Commands:
  incoming  Incoming reviews (not mine)
  merged    merged in the last number of days
  owned     Changes originated from current user (implicit)
```

## Contributing

Are you missing a feature, just check if there is a bug open for it and add
a new one if not. Once done, you are welcomed to make a PR that implements
the missing change.

## Related tools

* [git-review][4] is the git extension for working with gerrit, where I am also
  one of the core contributors.
* [gertty](https://opendev.org/ttygroup/gertty) is a very useful tui for gerrit
  which inspired me but which presents one essential design limitation: it does
  not work with multiple Gerrit servers.
* [gerrit-view](https://github.com/Gruntfuggly/gerrit-view) is a vscode plugin
  that can be installed from [Visual Studio Marketplace][3].

## Notes

1. `gri` name comes from my attempt to find a short name that was starting
   with **g** (from git/gerrit) and preferably sounds like `cli`.

[1]: https://github.com/pycontribs/gri/blob/master/test/gri.yaml
[2]: https://opendev.org/ttygroup/gertty/src/branch/master/examples/minimal-gertty.yaml
[3]: https://marketplace.visualstudio.com/items?itemName=Gruntfuggly.gerrit-view
[4]: https://docs.openstack.org/infra/git-review/
