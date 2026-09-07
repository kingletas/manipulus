# Manipulus_Bundles

A small Magento 2 module that does two jobs for [manipulus](https://github.com/kingletas/manipulus):

1. **It tells RequireJS about the bundles.** The map of which module lives in which bundle
   is contributed as a normal `requirejs-config.js`, so Magento merges it the way it merges
   every other module's.
2. **It keeps the integrity hashes honest.** Magento applies subresource integrity to
   payment pages. Change the merged `requirejs-config.js` and its recorded hash stops
   matching, the browser refuses the script, and checkout renders a spinner for ever with
   nothing in the console. `bin/magento manipulus:integrity:refresh` puts them back in step.

## Why a module at all

The deployed `requirejs-config.js` cannot simply be edited. Every versioned static request
in developer mode goes through `static.php`, which re-merges that file from source and
discards anything that was appended to it. A module is the only place the map survives.

## Installing

`manipulus build --module app/code/Manipulus/Bundles` writes this module into your
Magento tree with the bundles map filled in. Then:

```
bin/magento module:enable Manipulus_Bundles
bin/magento setup:upgrade
bin/magento setup:static-content:deploy -f
```

Deploying static content **after** enabling the module is what keeps the integrity hashes
right, because Magento generates the merged config and its hash together.

## Commands

| Command | What it does |
|---|---|
| `manipulus:integrity:refresh` | Recompute the recorded hashes from the files. `-n` reports without writing. |
| `manipulus:bundles:show` | List the deployed bundles and their sizes. |

Run the refresh whenever a deployed static file changes out of band — which in developer
mode is most of the time, because `static.php` rebuilds the merged config on request.

## Turning it off

`bin/magento module:disable Manipulus_Bundles`. There is deliberately no admin toggle: a
setting that needs a static content redeploy to take effect is not really a toggle, and
disabling the module is one command that always works.

## Licence

MIT.
