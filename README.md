# Manipulus

[![CI](https://github.com/kingletas/manipulus/actions/workflows/ci.yml/badge.svg)](https://github.com/kingletas/manipulus/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Manipulus works out which RequireJS modules each of your Magento 2 page types actually
loads, and bundles them so the browser fetches three files instead of a hundred and fifty.

It reads your codebase. It doesn't drive a browser, it doesn't need Node, and it doesn't
need your store to be running.

```
docker run --rm -v /path/to/magento:/magento:ro -v "$PWD:/out" manipulus:latest \
    plan --root /magento --theme frontend/Magento/luma --out /out/manipulus.plan.json
```

## Documentation

| | |
|---|---|
| [From nothing to a bundled storefront](docs/from-nothing.md) | Start here. A real store, taken from 226 JavaScript requests to 15. |
| [How it works](docs/how-it-works.md) | The four stages, and what each one can and cannot see. |
| [The Magento module](dist/magento/README.md) | What it does, and the trap that breaks checkout without it. |

## Why this exists

The usual tool for this job is [magepack](https://github.com/magesuite/magepack), and it
works by launching headless Chrome, loading each page type, and reading RequireJS's
runtime registry to see what got loaded. That approach is sound, but it means you need a
running store, a browser, a Node toolchain, and a URL for every page type. magepack's last
release was October 2022 and it still pins Puppeteer 2.1.1, which ships a Chromium from
February 2020.

Manipulus takes the other route. Everything RequireJS resolves at runtime is already
written down in your codebase:

- Magento merges every module's `requirejs-config.js` into one file when you deploy static
  content, so the `map`, `paths`, `shim`, `deps` and `mixins` tables are all in one place.
- Over 99% of `define()` calls list their dependencies as a literal array, so the graph can
  be walked without executing anything.
- The UI component names that look like they only exist at runtime are declared in layout
  XML, in `jsLayout` arguments.

So Manipulus parses all of that with a real JavaScript parser and computes the same answer,
deterministically, in a few seconds.

## What you get that a browser-driven tool can't give you

**It tells you why.** Every module in a bundle carries the chain that pulled it in.

```
$ manipulus explain Amasty_SocialLogin/js/authentication-popup-mixin
Amasty_SocialLogin/js/authentication-popup-mixin
  bundle: cart
  reached by product: PayPal_Braintree/js/paypal/product-page
  reached by cart: Magento_Checkout/js/proceed-to-checkout
```

**It refuses to write a half-finished bundle.** If a module can't be read, the run fails
and nothing is written. A bundle that's silently missing a module breaks a page you weren't
testing, days later.

**It's honest about what it left out.** Remote CDN scripts, modules another module registers
at runtime, and Magento's per-request translation file can't go in a bundle. Manipulus lists
them rather than quietly dropping them.

## Installing

**As a container**, which needs nothing but Docker:

```
git clone https://github.com/kingletas/manipulus && cd manipulus
make image
```

**On your machine**, which needs [uv](https://docs.astral.sh/uv/):

```
make install
```

## Using it

Three steps. Look at the graph, decide the bundles, write them.

```
manipulus graph --root /path/to/magento --theme frontend/Magento/luma
manipulus plan  --root /path/to/magento --theme frontend/Magento/luma
manipulus build --root /path/to/magento --theme frontend/Magento/luma
```

`build` takes `-n` to show you what it would write without writing it. Always run that first.

### Where a module several pages load ends up

A RequireJS bundles map records one owner per module, so a module cannot sit in two
bundles. `--common` decides where the shared ones go:

- **`cluster`**, the default. Each group of page types that shares enough modules gets
  its own bundle, so a home page does not carry checkout code. A group smaller than the
  minimum goes to `common` instead, because one extra request for a handful of modules
  costs more than carrying them everywhere.
- **`shared`**. Everything two or more pages load goes to `common`. Every page then
  fetches exactly two files, at the cost of carrying code it will not run.

Whichever you pick, the planner refuses to write a plan that places a module twice, and
names the module and the bundles that wanted it.

### Sharpening a page type with a real URL

The static pass finds entry points from layout XML and templates. A handful of components
are chosen at runtime by configuration — which payment methods are on, which widgets a CMS
page holds — and those only appear once the page is rendered.

If you have a running store, point Manipulus at a page and it will harvest the rendered
entry points too. This still doesn't use a browser: it's an HTTP GET and an HTML parse,
and nothing on the page is executed.

```
manipulus plan --root /path/to/magento \
    --url product=https://store.test/some-product.html \
    --url checkout=https://store.test/checkout/
```

The plan records which page types were sharpened this way, so an approximation is never
mistaken for an exact answer.

### Evidence on top of the layout, or instead of it

By default a rendered page is added to what the templates said. `--url-entries only` makes
it the whole answer for that page type instead.

```
manipulus plan --root /path/to/magento --url-entries only \
    --url category=https://store.test/some-category.html
```

The two answer different questions. The layout pass asks what a page of this type *could*
load, which is a union over every variant of it. A rendered page says what one real page
*did* ask for, which is smaller and blind to anything that page did not happen to render.

Measured on a store with 578,000 products and a custom theme, `only` took the shared bundle
from 270 modules to 158, and a category page from 3,862 KB to 3,213 KB with the same
components initialising. **Nothing breaks when it guesses low**: a module in no bundle is
fetched on its own, which costs a request rather than a feature.

`add` stays the default, because the safe failure is carrying a module you did not need.

### Deferring what nothing waits for

A `define([...])` dependency has to be there before the factory runs. An array-form
`require([...], callback)` is asynchronous, so nothing waits for it. `--defer` puts modules
reached only that way into bundles of their own, which RequireJS fetches when something
finally asks.

```
manipulus plan --root /path/to/magento --defer
```

**Expect this to be small.** On the store above it moved 13 modules out of 816. It is
correct, it costs nothing, and it is not where the weight is.

### Wiring the bundles into Magento

`build --module app/code/Manipulus/Bundles` writes the bundles and installs a small Magento
module that tells RequireJS about them:

```
manipulus build --root /path/to/magento --module app/code/Manipulus/Bundles
bin/magento module:enable Manipulus_Bundles
bin/magento setup:upgrade
bin/magento setup:static-content:deploy -f
```

**The deployed `requirejs-config.js` cannot simply be edited.** Every versioned static
request in developer mode goes through `static.php`, which re-merges that file from source
and discards anything appended to it. A module is the only place the map survives.

The module also carries `bin/magento manipulus:integrity:refresh`. Magento applies
subresource integrity to payment pages, so once the merged config changes its recorded hash
no longer matches, the browser refuses the script, and **checkout renders a spinner for ever
with nothing in the console**. Deploying static content after enabling the module keeps them
in step; run the command after any out-of-band change.

## What is in here

```
src/manipulus/
  analysis/     reading a deployed theme: its config, its modules, its CSS
  bundling/     deciding what goes in each bundle, and writing them out
  magento/      things true of the installation rather than of the theme
  cli.py
dist/magento/   the Magento module, with its own suite and its own Makefile
docs/           how it works
packaging/      release plumbing
```

`dist/` is what this project ships besides the command itself. The Magento module there is
real source with its own tests, not something generated a line at a time — `build --module`
copies it and fills in the bundles map.

Its checks need `magento/framework`, which resolves only from repo.magento.com:

```
make magento-install    # needs credentials
make magento            # the module's lint, coding standard, static analysis and unit suite
make check-all          # both projects at once
```

## Checking a plan is still good

`manipulus check` says nothing when the plan matches what's deployed, and names what's
wrong when it doesn't. Run it after a deploy — a plan built against an older static
content deploy will quietly reference modules that have moved.

## Checking a deploy is still sound

`manipulus check` reads a plan. `manipulus verify` reads what is actually deployed, which
is a different question and the one a browser answers.

```
manipulus verify --root /path/to/magento
manipulus verify --root /path/to/magento --url https://store.test/some-category.html
```

It is silent and exits 0 when the deploy is sound. It exits 1 and names the problem when a
bundle the map promises is not deployed, when a bundle claims a module it does not define,
or, with `--url`, when a script the page asks for is one the server will not hand over.

**This is worth having in a deploy pipeline.** The fault it exists for was found on a real
store: a static content deploy moved the version forward, nothing rebuilt the bundles
behind it, and every page referenced two files that returned 404. No log said so, no check
failed, and the page still rendered. The store served 2.7 MB of JavaScript in roughly 170
separate requests instead of two, for as long as nobody opened a browser network panel.

## What it can't do

- **It won't help with `customer/section/load`.** That request is uncacheable, it boots all
  of Magento, and no amount of bundling touches it. On most stores it costs more than the
  JavaScript does. Measure it before you assume bundling is your bottleneck.
- **It can't resolve a computed dependency.** `require([someVariable])` has no literal to
  read. There are usually only a couple in a whole theme, and `graph -v` lists them.
- **It doesn't minify.** It bundles the files Magento deployed. If you deploy with
  minification on, the bundle is already minified. It keeps its plain `bundle-<name>.js`
  name either way, and the module tells Magento not to ask for a `.min.js` copy of it.

## Licence

MIT. See [LICENSE](LICENSE).
