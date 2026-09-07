# Security

## Reporting a vulnerability

Email <code@kingletas.com>. Please don't open a public issue for a security problem.

Say what you found, how to reproduce it, and what you think the impact is. You'll get an
acknowledgement within a few days.

## What this tool touches

Manipulus reads a Magento installation and writes bundle files into its deployed static
content directory. It's worth knowing:

- **It reads and parses untrusted JavaScript.** Every file under the deployed theme is
  parsed. Parsing is done with tree-sitter and nothing is executed, but a hostile file
  could still make the parser work hard.
- **`--url` makes an outbound HTTP request** to whatever address you give it, and parses
  the HTML that comes back. Nothing in that HTML is executed. Only point it at a store
  you control.
- **`build` writes into your static content directory.** It only writes under a
  `manipulus/` subdirectory, and it refuses to write anything at all if any module in the
  plan can't be read.
- **The container runs as a non-root user** and expects the Magento tree mounted
  read-only for `graph` and `plan`.

## Supported versions

The most recent release gets security fixes.
