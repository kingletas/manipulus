# Manipulus

Manipulus works out which RequireJS modules each of your Magento 2 page types actually
loads, and bundles them so the browser fetches three files instead of a hundred and fifty.

It reads your codebase. It doesn't drive a browser, it doesn't need Node, and it doesn't
need your store to be running.

```
docker run --rm -v /path/to/magento:/magento:ro -v "$PWD:/out" manipulus:latest \
    plan --root /magento --theme frontend/Magento/luma --out /out/manipulus.plan.json
```

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

### Wiring the bundles into Magento

`build` writes the bundles and a `requirejs-bundles-config.js` beside them, under
`pub/static/<area>/<Vendor>/<theme>/<locale>/manipulus/`. Load that config file after
Magento's own `requirejs-config.js` and RequireJS will fetch a bundle instead of each
module in it.

## Checking a plan is still good

`manipulus check` says nothing when the plan matches what's deployed, and names what's
wrong when it doesn't. Run it after a deploy — a plan built against an older static
content deploy will quietly reference modules that have moved.

## What it can't do

- **It won't help with `customer/section/load`.** That request is uncacheable, it boots all
  of Magento, and no amount of bundling touches it. On most stores it costs more than the
  JavaScript does. Measure it before you assume bundling is your bottleneck.
- **It can't resolve a computed dependency.** `require([someVariable])` has no literal to
  read. There are usually only a couple in a whole theme, and `graph -v` lists them.
- **It doesn't minify.** It bundles the files Magento deployed. If you deploy with
  minification on, the bundle is already minified.

## Licence

MIT. See [LICENSE](LICENSE).
