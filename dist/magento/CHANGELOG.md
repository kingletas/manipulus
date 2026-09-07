# Changelog

All notable changes to this module are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This module ships inside [manipulus](https://github.com/kingletas/manipulus) and its
version tracks that project's.

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
