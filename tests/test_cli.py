"""The build command against a deployed theme, minified by Magento or not."""

import re
from pathlib import Path

import pytest

from manipulus import cli
from manipulus.bundling import bundler
from manipulus.bundling import plan as plan_module
from manipulus.bundling.plan import Bundle, Plan

THEME = "frontend/Vendor/theme"
LOCALE = "en_US"
CONFIG = "require.config({ map: { '*': { entry: 'Vendor_Mod/js/entry' } } });"


def deployed_store(tmp_path: Path, minified: bool) -> Path:
    """One deployed theme, its files named as Magento names them with minification on or off."""
    suffix = ".min.js" if minified else ".js"
    theme_root = cli.theme_root_for(tmp_path, THEME, LOCALE)
    (theme_root / "Vendor_Mod" / "js").mkdir(parents=True)
    (theme_root / f"requirejs-config{suffix}").write_text(CONFIG)
    (theme_root / "Vendor_Mod" / "js" / f"entry{suffix}").write_text(
        "define(['Vendor_Mod/js/leaf'],function(){});"
    )
    (theme_root / "Vendor_Mod" / "js" / f"leaf{suffix}").write_text("define([],function(){});")
    return tmp_path


def build(root: Path) -> int:
    plan = Plan(
        theme=THEME,
        locale=LOCALE,
        bundles=[Bundle(name="common", modules=["Vendor_Mod/js/entry", "Vendor_Mod/js/leaf"])],
    )
    plan_file = root / "manipulus.plan.json"
    plan_module.write(plan, plan_file)
    argv = ["build", "--root", str(root), "--theme", THEME, "--locale", LOCALE, "--jobs", "1"]
    return cli.main([*argv, "--plan", str(plan_file)])


JS_EXCLUDES = re.compile(r"<js>.*?<minify_exclude>(.*?)</minify_exclude>", re.S)
EXCLUDE_ENTRY = re.compile(r"<([\w.-]+)>([^<]*)</\1>")


def shipped_js_excludes() -> list[str]:
    config = (bundler.module_source() / "etc" / "config.xml").read_text("utf-8")
    block = JS_EXCLUDES.search(config)
    assert block, "etc/config.xml declares no JavaScript minification exclusions"
    return [value.strip() for _, value in EXCLUDE_ENTRY.findall(block.group(1))]


def magento_excludes(path: str) -> bool:
    """Minification::isExcluded, which decides whether Magento and RequireJS add `.min`."""
    return any(re.search(expr.replace("/", r"\/"), path) for expr in shipped_js_excludes())


@pytest.mark.parametrize("minified", [False, True], ids=["plain", "minified"])
def test_a_bundle_keeps_its_plain_name_either_way(tmp_path, minified):
    root = deployed_store(tmp_path, minified)

    assert build(root) == 0

    bundle_dir = cli.theme_root_for(root, THEME, LOCALE) / bundler.BUNDLE_DIR
    assert sorted(p.name for p in bundle_dir.glob("bundle-*")) == ["bundle-common.js"]
    body = (bundle_dir / "bundle-common.js").read_text()
    assert 'define("Vendor_Mod/js/entry"' in body
    assert 'define("Vendor_Mod/js/leaf"' in body


def test_minification_leaves_every_bundle_path_alone():
    """RequireJS asks for the plain name only when the module's exclusion matches it."""
    for name in ("common", "product", "checkout"):
        path = f"{THEME}/{LOCALE}/{bundler.BUNDLE_DIR}/bundle-{name}.js"
        assert magento_excludes(path), f"{path} would be requested as .min.js"


def test_minification_still_applies_to_everything_else():
    theme_root = f"{THEME}/{LOCALE}"
    assert not magento_excludes(f"{theme_root}/Vendor_Mod/js/entry.js")
    assert not magento_excludes(f"{theme_root}/{bundler.BUNDLE_DIR}/requirejs-bundles-config.js")


def test_a_theme_with_no_deployed_config_names_both_files(tmp_path, capsys):
    cli.theme_root_for(tmp_path, THEME, LOCALE).mkdir(parents=True)

    with pytest.raises(SystemExit) as stopped:
        build(tmp_path)

    assert "requirejs-config.min.js or requirejs-config.js" in str(stopped.value)
