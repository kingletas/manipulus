# Contributing

Thanks for taking a look.

## Getting set up

You need [uv](https://docs.astral.sh/uv/). Everything else it installs for you.

```
make setup
make check
```

`make check` runs the linter and the test suite, and it's what a commit has to pass.

## Where things live

```
src/manipulus/analysis/    reading a deployed theme: config, modules, CSS
src/manipulus/bundling/    deciding what goes in each bundle, and writing them
src/manipulus/magento/     things true of the installation, not of the theme
dist/magento/              the Magento module, with its own suite
```

`tests/` mirrors `src/manipulus/`. A new module goes in the package that matches what it
reads or writes, and its test goes in the same place under `tests/`.

## Working on it

- `make test` runs the suite. `make lint` runs ruff. `make format` rewrites files in house
  style and fixes what it can.
- `make image` builds the container.
- `make magento` runs the Magento module's own suite — 16 unit tests, a wiring test, the
  Magento coding standard and static analysis. It needs `make magento-install` first, which
  resolves `magento/framework` and so needs repo.magento.com credentials. `make check-all`
  runs both projects.
- Point the tool at a real store to try a change: `make plan ROOT=/path/to/magento`.

## Things worth knowing before you change the parser

**The merged `requirejs-config.js` is not one config.** It's a hundred-odd IIFEs, each with
its own `var config = {...}` and its own `require.config(config)` call. Resolving that name
across the whole file makes every block read as the last one, and the merged result looks
plausible while being almost entirely wrong. Name resolution is scoped to the block that
declares it, and `test_each_iife_config_is_read_not_only_the_last` is the guard.

**Nothing is dropped in silence.** If a module can't be read, the build fails and writes
nothing. If a dependency can't go in a bundle, it's recorded and reported. This is the
whole point of the tool, and a change that turns a failure into a debug log will be
rejected.

**Test both directions.** A test that proves the tool works when everything is fine proves
nothing about whether it can report a problem. Every check needs a test that makes it fire
and a test that makes it stay quiet.

## Writing tests

Tests live in `tests/` and use pytest; the Magento module's live in `dist/magento/Test/Unit`
and use PHPUnit. Build fixtures out of invented data shaped like the
real thing rather than copying a real store's files.

Name a test after the behaviour it pins down, not the function it calls.
`test_a_missing_module_refuses_the_whole_run` tells you what broke when it fails;
`test_build_bundles_2` doesn't.

## Pull requests

Keep the change and its tests together. Update `CHANGELOG.md` under an `## [Unreleased]`
heading. If you're changing what a command prints, update the README too.
