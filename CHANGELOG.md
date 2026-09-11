# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **An enabled `Manipulus_Bundles` no longer breaks the storefront in developer mode.** Switching to developer mode empties `pub/static`, but the module still contributed its bundles map, so RequireJS asked for bundles that were gone and a product page's JavaScript never started. The module now leaves the map out whenever a bundle it names is missing for the theme and locale being rendered. A static content deploy still keeps it, because `manipulus build` writes the bundles after the deploy, so production behaves as before.
- **Manipulus works on a store that minifies JavaScript.** Magento deploys the merged config as `requirejs-config.min.js` there, and `graph`, `plan`, `build` and `check` only looked for `requirejs-config.js`, so each stopped with "no requirejs-config.js". They now read whichever of the two is deployed.
- **The bundles load on a store that minifies JavaScript.** RequireJS asked for `bundle-<name>.min.js`, which `build` never wrote, so every bundle 404'd. `Manipulus_Bundles` now puts the bundle path on Magento's minification exclusion list, so RequireJS asks for the `bundle-<name>.js` that `build` writes. Deploy static content after enabling the module, as before, for the exclusion to reach RequireJS.
- The module's README said `manipulus:integrity:refresh -n` reports without writing. The option is `--dry-run`, because the console reserves `-n`.
- **`make check` passes on a CI runner.** The private-info sweep flagged the runner's own login, `runner`, wherever the word appeared in prose. On CI it now skips the login and hostname checks, which only mean something on the author's machine, and still checks for home paths and personal source trees.

### Changed

- CI runs `make check`, so the private-info sweep runs on every push, and a newer push cancels the run it replaces.
- Dependabot groups its updates into one pull request per ecosystem.

## [0.5.0] - 2026-09-07

### Changed

- **The codebase is no longer flat.** `src/manipulus/` is three packages now — `analysis`
  for reading a deployed theme, `bundling` for deciding and writing, `magento` for things
  true of the installation rather than of the theme. The test tree mirrors it.
- **The Magento module moved to `dist/magento`**, which is where this project puts what it
  ships besides the command itself.

### Added

- **The Magento module has its own suite**: 16 unit tests over its two commands and its
  hash model, a wiring test that reads `etc/di.xml` against the code it names, Magento's
  coding standard, static analysis at level 6, and a Makefile. `make magento` runs them.
- A release workflow, a Dependabot configuration and a changelog extractor, so a tag
  publishes a release whose body is that version's changelog section.

### Fixed

- `build --module` copied everything beside the module source, so running it from a
  checkout where `composer install` had been run would have written **180 MB of Magento
  framework** into the store's `app/code`.
- The module set an area code it did not need, and caught the "already set" exception with
  an empty body — which is a coding-standard warning and, more to the point, was doing
  nothing.

## [0.4.0] - 2026-09-07

### Added

- **A real Magento module**, `Manipulus_Bundles`, kept as source under `magento-module/`
  rather than generated line by line. `build --module DIR` copies it and fills in the
  bundles map. It ships a `composer.json`, a module sequence that puts it after
  `Magento_RequireJs` and `Magento_Csp`, and two commands a deploy pipeline can run
  without manipulus installed:
  - `bin/magento manipulus:integrity:refresh` recomputes the subresource integrity
    hashes. This is the one that stops checkout breaking.
  - `bin/magento manipulus:bundles:show` lists the deployed bundles and their sizes.

### Fixed

- A bundle from a previous plan was left on disk when the new plan no longer had it. It
  was still served and still listed, so it read as current while describing modules that
  may have moved. `build` now removes them.

## [0.3.0] - 2026-09-07

Checkout verified with bundles: 230 JavaScript requests down to 16, the same 501 modules,
and the page renders and functions.

### Added

- `manipulus sri` refreshes Magento's subresource integrity hashes. Magento applies SRI to
  payment pages, so once the merged `requirejs-config.js` changes, its recorded hash no
  longer matches, the browser silently refuses the script and checkout renders a spinner
  for ever. Nothing warns. Run this after any change to a deployed file the store hashes.
- `manipulus css` reports the stylesheets a theme deploys and, given a URL, how many of
  each one's class names appear in the rendered markup. **It is a floor, not a verdict** —
  a class JavaScript adds after load is invisible to it.
- `manipulus plan --common shared` promotes a module wanted by two or more page types into
  the common bundle instead of leaving it in each. Neither answer is free and the plan
  records which produced it.

### Fixed

- A module wanted by several page types was written into every one of their bundles and
  declared more than once in the RequireJS map, so its bytes shipped repeatedly and only
  one claim decided where it was looked for — which is how a cart page ended up fetching
  the product bundle. 134 of 557 modules were in that state.

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
