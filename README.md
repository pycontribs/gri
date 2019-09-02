# gri : Gerrit Reduced Interface

`gri`[¹](#f11) is a CLI tool that will list your open git reviews from multiple servers
in a way that makes easier to to identify which one need.

![screenshot](https://repository-images.githubusercontent.com/205845628/4a76fd00-ce23-11e9-8d12-162184df41c5)

## Features
* multiple Gerrit servers
* change number and topics are clickable links
* draft/dnm/wip changes are grayed out

## Wishlist

* Configurable Gerrit servers
* Sorting :: top ones should be those closer to be merged
* Grouping
* Caching
* Dependency graph based on zuul Depends-On
* Configurable query
* Include starred changes
* Zuul build status support
* top mode :: so it can auto-refresh and notify you of important changes

## Installing
```
pip install gri
```

## Usage
Currently the tool loads gerrit servers defined in [`~/.gertty.yaml`][1] but
uses credentials from `~/.netrc` file.

So use it just run `gli`, or `python -m gri`.

## Contributing
Are you missing a feature, just check if there is a bug open for it and add
a new one if not. Once done, you are welcomed to make a PR that implements
the missing change.

## Related tools
* [GerTTY](https://github.com/openstack/gertty) is a very useful tui for gerrit
which inspired me but which presents one essential design limitation: it does
not work with multiple Gerrit servers.

## Notes
1. <span id="f1"></span> The reality is that `gri` name comes from my attempt to
find a short namespace on pypi that was starting with g (from Gerrit) and
preferably sounds like `cli`, most were taken. You are welcomed to propose
better acronym expansions.

[1]: https://github.com/openstack/gertty/tree/master/examples
