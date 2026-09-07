# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-09-07

Verified end to end against a running Magento 2.4.8 store with sample data. Loading a
product page with the generated bundles took it from **226 JavaScript requests to 15**,
with the same 355 modules in the RequireJS registry and no new console errors.

### Added

- `manipulus build --module DIR` emits a small Magento module that contributes the
  bundles map. This is the only wiring that works: every versioned static request in
  developer mode goes through `static.php`, which re-merges `requirejs-config.js` from
  source and discards anything appended to the deployed copy.

### Fixed

- **`paths` decided the module id.** It does not: `paths` says where a module's *file*
  lives, and the id keeps the name it was asked for. RequireJS asks for `spectrum`, so a
  bundle declaring `jquery/spectrum/spectrum` claimed an id nothing requests and the
  module loaded on its own anyway. `resolve()` now returns the id and `path_for()` the
  location, with the file indexed under both names.
- **CommonJS dependencies were not read.** `define(function (require) { require('./dep') })`
  names dependencies inside the factory rather than in an array. Four files in a stock
  Luma tree use it and between them they pull in two dozen modules. Recall against the
  live registry went from 82.2% to 93.1%.

## [0.1.0] - 2026-09-07

First release.

### Added

- `manipulus graph` reports the AMD dependency graph for a deployed theme and locale,
  built by parsing every deployed JavaScript file with tree-sitter.
- `manipulus plan` decides a common bundle and one bundle per page type, from entry points
  collected out of layout XML, `jsLayout` component declarations and templates.
- `manipulus build` writes the bundles and the RequireJS `bundles` configuration that
  points at them. `-n` reports without writing.
- `manipulus explain` prints the chain of dependencies that pulled a module into a bundle.
- `manipulus check` is silent when a plan still matches what's deployed, and names what
  has drifted when it doesn't.
- Entry points can be sharpened from a running store with `--url`, using an HTTP GET and an
  HTML parse. No browser, and nothing on the page is executed.
- A container image, so a clone and `make image` is the whole install.

### Notes

- The merged `requirejs-config.js` is many separate IIFEs, each declaring its own
  `var config`. Resolving that name across the whole file makes all 126 blocks read as the
  last one; resolution is scoped to the block that declares it.
- A run that cannot read every module in a bundle writes nothing at all. Bundles are
  assembled in memory first, so a failure leaves no half-built file for RequireJS to find.
- Remote URLs, runtime-registered modules and Magento's per-request translation file are
  excluded from bundles and reported, never silently dropped.
