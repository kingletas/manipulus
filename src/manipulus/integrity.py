"""Keeps Magento's subresource integrity hashes in step with the files they describe."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

# Magento writes one hash file per area, next to the deployed themes.
HASH_FILE = "sri-hashes.json"


class IntegrityError(RuntimeError):
    """The integrity hash file could not be read or written."""


@dataclass
class IntegrityResult:
    path: Path
    refreshed: list[str]
    missing: list[str]
    unchanged: int


def hash_file(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


def hash_files(static_root: Path) -> list[Path]:
    return sorted(static_root.glob(f"*/{HASH_FILE}"))


def refresh(static_root: Path, dry_run: bool = False) -> list[IntegrityResult]:
    """Recompute every recorded hash from the file it describes.

    Magento applies subresource integrity to payment pages, so a stale hash does not
    warn: the browser refuses the script and checkout renders a spinner for ever. Any
    change to a deployed file the store hashes has to be followed by this.
    """
    results = []
    for hashes_path in hash_files(static_root):
        area = hashes_path.parent.name
        try:
            recorded = json.loads(hashes_path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise IntegrityError(f"could not read {hashes_path}: {error}") from error

        refreshed, missing, unchanged = [], [], 0
        for key in sorted(recorded):
            # Keys are area-relative, and the file sits in the area directory.
            relative = key[len(area) + 1 :] if key.startswith(area + "/") else key
            target = hashes_path.parent / relative
            if not target.is_file():
                missing.append(key)
                continue
            actual = hash_file(target)
            if recorded[key] == actual:
                unchanged += 1
            else:
                recorded[key] = actual
                refreshed.append(key)

        if refreshed and not dry_run:
            hashes_path.write_text(json.dumps(recorded), encoding="utf-8")
        results.append(IntegrityResult(hashes_path, refreshed, missing, unchanged))
    return results
