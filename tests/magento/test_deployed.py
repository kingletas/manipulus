"""Checking what is deployed, which is not what a plan says should be."""

from __future__ import annotations

import pytest

from manipulus.magento import deployed

CONFIG = """require.config({
    "bundles": {
        "manipulus/bundle-common": [
            "a/one",
            "a/two"
        ]
    }
});
"""


def _theme(tmp_path, config=CONFIG, bundle=None):
    root = tmp_path / "theme"
    (root / "manipulus").mkdir(parents=True)
    (root / deployed.BUNDLE_CONFIG).write_text(config)
    if bundle is not None:
        (root / "manipulus" / "bundle-common.js").write_text(bundle)
    return root


def test_a_sound_deploy_reports_nothing(tmp_path):
    bundle = "define('a/one',[],function(){});" + 'define("a/two",[],function(){});'
    root = _theme(tmp_path, bundle=bundle)

    assert deployed.verify_bundles(root) == []


def test_a_bundle_the_map_names_and_nobody_deployed_is_reported(tmp_path):
    """The fault that costs nothing at deploy time and every request after it."""
    root = _theme(tmp_path)

    findings = deployed.verify_bundles(root)

    assert len(findings) == 1
    assert "no file is deployed" in findings[0]


def test_a_bundle_that_claims_a_module_it_does_not_define_is_reported(tmp_path):
    """RequireJS waits forever for a module its map promised."""
    root = _theme(tmp_path, bundle="define('a/one',[],function(){});")

    findings = deployed.verify_bundles(root)

    assert len(findings) == 1
    assert "a/two" in findings[0]


def test_a_theme_with_no_bundles_config_says_so(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()

    with pytest.raises(deployed.DeployedError, match="no bundles config"):
        deployed.verify_bundles(root)


def test_a_config_this_tool_did_not_write_is_refused_rather_than_guessed_at(tmp_path):
    root = _theme(tmp_path, config="require.config({ paths: {} });")

    with pytest.raises(deployed.DeployedError, match="not one this tool wrote"):
        deployed.verify_bundles(root)


def test_both_quote_styles_count_as_a_definition():
    assert deployed.defined_modules("define(\"a\",[]);define('b',[]);") == {"a", "b"}


def test_an_anonymous_define_defines_nothing_by_name():
    assert deployed.defined_modules("define([], function () {});") == set()


def test_the_map_survives_the_shape_the_builder_writes():
    assert deployed.bundles_map(CONFIG) == {"manipulus/bundle-common": ["a/one", "a/two"]}
