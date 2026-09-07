# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

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
