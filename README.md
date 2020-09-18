# gri : Gerrit Reduced Interface

`gri` is a CLI tool that **lists git reviews** from multiple servers
in a way that makes easier to to identify which one need you attention.

![screenshot](https://sbarnea.com/ss/Screen-Shot-2020-09-18-10-41-05.06.png)

## Features

* combines results from multiple Gerrit servers
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

Currently the tool loads gerrit servers defined in [`~/.gertty.yaml`][1] but
uses credentials from `~/.netrc` file.

```shell
$ gri --help
Usage: gri [OPTIONS] COMMAND [ARGS]...

Options:
  -i, --incoming             Incoming reviews (not mine)
  -m, --merged INTEGER       merged in the last number of days
  -a, --abandon              Abandon changes (delete for drafts) when they are
                             >90 days old and with negative score. Requires -f
                             to perform the action.
  -z, --abandon-age INTEGER  default=90, number of days for which changes are
                             subject to abandon
  General options:
    -u, --user TEXT          Query another user than self
    -s, --server TEXT        [0,1,2] key in list of servers, Query a single
                             server instead of all
    -o, --output TEXT        Filename to dump the result in, currently only
                             HTML is supported
    -f, --force              Perform potentially destructive actions.
    -d, --debug              Debug mode
  --help                     Show this message and exit.
```

## Contributing

Are you missing a feature, just check if there is a bug open for it and add
a new one if not. Once done, you are welcomed to make a PR that implements
the missing change.

## Related tools

* [git-review][3] is the git extension for working with gerrit, where I am also
  one of the core contributors.
* [GerTTY](https://github.com/openstack/gertty) is a very useful tui for gerrit
  which inspired me but which presents one essential design limitation: it does
  not work with multiple Gerrit servers.
* [Gerrit-View](https://github.com/Gruntfuggly/gerrit-view) is a vscode plugin
  that can be installed from [Visual Studio Marketplace][2].

## Notes

1. `gri` name comes from my attempt to find a short name that was starting
   with **g** (from git/gerrit) and preferably sounds like `cli`.

[1]: https://github.com/openstack/gertty/tree/master/examples
[2]: https://marketplace.visualstudio.com/items?itemName=Gruntfuggly.gerrit-view
[3]: https://docs.openstack.org/infra/git-review/
