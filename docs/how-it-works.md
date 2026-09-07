# How Manipulus works

Four stages. Each one is a command you can run on its own, and each writes something you
can read.

## 1. Read the configuration

Magento merges every module's `requirejs-config.js` into a single file when you deploy
static content. On a real store that's a hundred and sixty separate files collapsed into
one, at:

```
pub/static/<area>/<Vendor>/<theme>/<locale>/requirejs-config.js
```

That merged file is not one configuration object. It's a long series of blocks that each
look like this:

```js
(function () {
    var config = { map: { '*': { ko: 'knockoutjs/knockout' } } };
    require.config(config);
})();
```

Every block declares its own `config`. There were 126 of them on the store this was built
against. **If you resolve the name `config` across the whole file, all 126 blocks read as
the last one** — and the merged result looks completely plausible while being wrong. So
each block's `config` is resolved inside the function that declares it.

What comes out is the `map`, `paths`, `shim`, `deps` and `mixins` tables, merged in
declaration order the way RequireJS merges them.

## 2. Build the dependency graph

Every `.js` and `.html` file under the deployed theme is parsed with tree-sitter, and the
dependency arrays are pulled out of `define()` and `require()` calls.

Four shapes turn up:

| Written as | What happens |
|---|---|
| `define(['a', 'b'], fn)` | both names are dependencies |
| `define('id', ['a'], fn)` | the second argument is the list |
| `define(fn)` | no dependencies |
| `define([someVariable], fn)` | can't be read, so it's reported |

That last row is rarer than you'd expect. On a 1,819-file theme there were two, and both
were inside RequireJS itself.

Then two things get added that aren't written in any file:

- **Shim dependencies**, for scripts that aren't AMD modules at all.
- **Mixins.** Magento's mixin system makes a module load whenever its target loads, and
  that relationship only exists in the config. This is the main reason a naive graph walk
  misses things: extension mixins are invisible in the source of the module they modify.

## 3. Find the entry points

An entry point is a module a page asks for directly. There are three places they live, and
Manipulus reads all three.

**Layout XML `jsLayout` declarations.** This is the big one, and it's why the static pass
gets close to a browser-driven one. UI components look like they only exist at runtime,
because the template just calls `$block->getJsLayout()`. But the component names are
declared right there in the layout file:

```xml
<item name="component" xsi:type="string">Magento_Checkout/js/view/progress-bar</item>
```

Adding this took the checkout bundle from 77 modules to 395.

**Templates.** `x-magento-init` blocks and `data-mage-init` attributes in `.phtml` files
reachable from a page type's layout handles.

**Rendered HTML, if you give it a URL.** Some components are chosen by configuration —
which payment methods are enabled, what a CMS page contains — and only appear once the
page renders. An HTTP GET and an HTML parse picks those up. No browser, and nothing on the
page is executed.

The plan records which page types were sharpened with a URL, so you always know whether a
number is exact or an approximation.

## 4. Decide and write the bundles

For each page type, walk the graph out from its entry points plus the always-loaded `deps`.
Whatever every page type loads becomes the `common` bundle; the rest becomes that page
type's own bundle. Checkout doesn't get a vote on what's common, because it loads far more
than anything else and would drag the common bundle up for every other page.

Modules are wrapped as they're concatenated, because a file that shares a bundle has to be
able to say its own name:

| Kind | What happens |
|---|---|
| `define('id', ...)` | left alone, it already knows its name |
| `define(...)` | its name is inserted |
| not an AMD module | wrapped in a `define` that reads its shim config |
| an `.html` template | wrapped in a `define` that returns its text |

Nothing is written until every bundle has been assembled successfully. If a single module
can't be read, the run fails and the directory is left as it was.

## What stays outside a bundle

Three kinds of dependency can't be bundled, and all three are listed rather than dropped:

- **Remote URLs.** Braintree, Cardinal, Google Pay, Cloudinary. RequireJS loads these from
  their own CDN and they aren't in your static tree.
- **Runtime-registered modules.** PayPal's SDK shim registers itself under a name nothing
  on disk provides.
- **Generated files.** `js-translation.json` is written per request, so a build-time copy
  would be wrong.
