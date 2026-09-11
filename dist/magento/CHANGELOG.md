# Changelog

All notable changes to this module are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This module ships inside [manipulus](https://github.com/kingletas/manipulus) and its
version tracks that project's.

## [Unreleased]

### Fixed

- The bundles map is left out of the merged `requirejs-config.js` whenever a bundle it names
  is missing for the theme and locale being rendered. Developer mode empties `pub/static`,
  and with the map still in place RequireJS asked for bundles that were gone and a product
  page's JavaScript never started.

### Notes

- A merge on the command line always keeps the map. That is where
  `setup:static-content:deploy` runs, and it runs before `manipulus build` writes the
  bundles, so checking there would take the map out of every production deploy.
- The check looks for the file RequireJS will actually request, so with JavaScript
  minification on it looks for `bundle-<name>.min.js`.

## [0.5.0] - 2026-09-07

### Added

- `manipulus:integrity:refresh` recomputes the subresource integrity hashes Magento
  records for deployed static files. Magento applies integrity to payment pages, so once
  the merged `requirejs-config.js` changes its recorded hash no longer matches, the browser
  refuses the script, and checkout renders a spinner for ever with nothing in the console.
- `manipulus:bundles:show` lists the deployed bundles and their sizes, so a release can be
  checked without opening a browser.
- The bundles map itself, contributed as an ordinary `requirejs-config.js` for Magento to
  merge. `manipulus build --module` fills it in.
- A unit suite, a coding-standard configuration and static analysis.

### Notes

- The command names are class constants rather than `di.xml` arguments. They were tried as
  wiring first, which is what the estate's own rule prefers, and Magento's generated
  interceptor did not receive the argument — the commands registered with an empty name
  and refused to run. A distributable command owns its name anyway: renaming it breaks
  every pipeline that calls it.
- The module does not set an area code. It did, and catching the "already set" exception
  with an empty body is a coding-standard warning; nothing it does depends on an area.
