# From nothing to a bundled Magento storefront

By the end of this you'll have taken a Magento 2 store from 226 JavaScript requests on a
product page down to 15, and you'll be able to say why every module ended up where it did.

Everything below was run against a stock Magento 2.4.8 with the standard sample data.

## Contents

- [What this is](#what-this-is)
- [Step 1: install it](#step-1-install-it)
- [Step 2: look at the graph](#step-2-look-at-the-graph)
- [Step 3: decide the bundles](#step-3-decide-the-bundles)
- [Step 4: write them, and the module that loads them](#step-4-write-them-and-the-module-that-loads-them)
- [Step 5: turn it on](#step-5-turn-it-on)
- [Step 6: check it worked](#step-6-check-it-worked)
- [When something looks wrong](#when-something-looks-wrong)

## What this is

Magento's storefront loads its JavaScript as a few hundred separate files, resolved in the
browser by RequireJS. Every one of them is a request. Bundling groups them so the browser fetches a
handful of files instead.

The usual tool for this drives a headless Chrome at your store to find out what each page
loads. This one reads your codebase instead, because everything the browser would find out is already written down: Magento merges every module's `requirejs-config.js` when you deploy
static content, over 99% of `define()` calls list their dependencies literally, and the UI
component names that look like they only exist at runtime are declared in layout XML.

So there's no browser, no Node, and the store doesn't even have to be running.

## Step 1: install it

Either as a container, which needs nothing but Docker:

```bash
git clone https://github.com/kingletas/manipulus && cd manipulus && make image
```

Or on your machine, which needs [uv](https://docs.astral.sh/uv/):

```bash
make install
```

The examples below use the local command. For the container, replace `manipulus` with
`docker run --rm -v /path/to/magento:/magento:ro manipulus:latest` and use `/magento` as
the root.

## Step 2: look at the graph

Point it at a Magento installation and a deployed theme. Nothing gets written yet.

```bash
manipulus graph --root /path/to/magento --theme frontend/Magento/luma --locale en_US
```

```text
theme          /path/to/magento/pub/static/frontend/Magento/luma/en_US
config blocks  65
modules        1530
edges          3685
dynamic deps   18 file(s) name a dependency this cannot resolve
external       29 dependencies left outside bundles
```

**If this fails with "no requirejs-config.js", deploy static content first.** It reads what Magento deployed, not what your modules contain:

```bash
bin/magento setup:static-content:deploy -f en_US --theme Magento/luma
```

`dynamic deps` are the handful of places where a dependency is worked out at runtime rather than written down. `external` is what can't go in a bundle at all — remote CDN scripts, modules another
module registers at runtime, and Magento's per-request translation file. Both are listed
rather than quietly dropped; `graph -v` names them.

## Step 3: decide the bundles

```bash
manipulus plan --root /path/to/magento --theme frontend/Magento/luma
```

```text
plan written to manipulus.plan.json   (common: intersect)
  common         161 modules   (static)
  cart           133 modules   (static)
  category        14 modules   (static)
  checkout       260 modules   (static)
  product         59 modules   (static)
  unbundled     1023 modules reached by no page type
```

That's worked out with no contact with your store at all.

A handful of components are chosen by configuration rather than by code — which payment
methods are on, what a CMS page contains — and only show up once a page renders. If the store's running, point at a few pages and those get picked up too. It's still not a browser: it's an HTTP GET and an HTML parse, and nothing on the page is executed.

```bash
manipulus plan --root /path/to/magento \
    --url product=https://your-store/some-product.html \
    --url checkout=https://your-store/checkout/
```

On the store this was measured against, the live pages added 38 modules the codebase alone couldn't see — and contradicted none of it.

## Step 4: write them, and the module that loads them

```bash
manipulus build --root /path/to/magento --module app/code/Manipulus/Bundles -n
```

`-n` reports without writing. **Run that first.** Drop the `-n` once it looks right.

```text
  wrote bundle-common.js               161 modules      1970 kB
  wrote bundle-cart.js                 133 modules       364 kB
  wrote bundle-checkout.js             260 modules       709 kB
  wrote Manipulus_Bundles into app/code/Manipulus/Bundles
  total 3137 kB
```

If any module in the plan cannot be read, **nothing is written at all**. A bundle that's quietly missing a module breaks a page you weren't testing, days later.

## Step 5: turn it on

```bash
bin/magento module:enable Manipulus_Bundles && bin/magento setup:upgrade
```

Then deploy static content **after** enabling it:

```bash
bin/magento setup:static-content:deploy -f
```

That order matters. Magento generates the merged `requirejs-config.js` and its subresource
integrity hash together, so doing it this way round keeps them in step.

## Step 6: check it worked

Load a product page and count the JavaScript requests in your browser's network panel.
Before, this store made 226. Afterwards, 15.

From the command line:

```bash
bin/magento manipulus:bundles:show
```

And ask why any module is where it is:

```bash
manipulus explain Magento_Customer/js/customer-data
```

```text
Magento_Customer/js/customer-data
  bundle: common
  reached by product: Magento_Customer/js/customer-data
  reached by checkout: Magento_Customer/js/customer-data
```

## When something looks wrong

**Checkout renders a spinner for ever, and the console says nothing.** This is the one worth knowing about. Magento applies subresource integrity to payment pages, so once anything changes the merged `requirejs-config.js` the recorded hash stops matching, and the browser quietly refuses the script:

```bash
bin/magento manipulus:integrity:refresh
```

It says nothing when they already agree.

**The commands are missing from `bin/magento list`.** Magento caches the merged `di.xml`,
and on a stack with Redis or Valkey behind the cache that lives in the cache server rather than in `var/cache`. Restart the PHP containers first and flush the cache server *after*
they are up — a container that's starting repopulates the cache from the state it had.

**A page loads a bundle it shouldn't need.** A module wanted by several page types has no obviously right home. `--common shared` promotes those to the common bundle instead; that costs every page a few more bytes, and removes the surprise. The plan records which was used.

## Where to go next

- [How it works](how-it-works.md) — the four stages, and what each one can and can't see.
- `manipulus css` — what your theme's stylesheets cost and how much of them a page uses.
  On stock Luma that's 923 kB of CSS with about 11% of its rules matching anything.
