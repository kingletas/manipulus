"""What may and may not go inside a bundle."""

import pytest

from manipulus.analysis.resolve import bundle_id, is_remote, split_plugin


@pytest.mark.parametrize(
    "name",
    [
        "https://js.braintreegateway.com/web/client.min.js",
        "http://example.test/a.js",
        "//product-gallery.cloudinary.com/latest/all",
    ],
)
def test_remote_names_are_never_bundled(name):
    assert is_remote(name)
    assert bundle_id(name) is None


def test_a_plain_module_keeps_its_id():
    assert bundle_id("Magento_Catalog/js/price-box") == "Magento_Catalog/js/price-box"


def test_a_text_resource_keeps_its_plugin_prefix():
    name = "text!Magento_Ui/templates/modal.html"
    assert bundle_id(name) == name


def test_a_dynamic_plugin_resource_is_left_out():
    assert bundle_id("domReady!") is None
    assert bundle_id("domReady!something") is None


def test_requirejs_pseudo_modules_are_left_out():
    assert bundle_id("require") is None
    assert bundle_id("exports") is None
    assert bundle_id("module") is None


def test_generated_translations_are_left_out():
    """Magento writes this per request, so a build-time copy would be wrong."""
    assert bundle_id("js-translation.json") is None


def test_split_plugin():
    assert split_plugin("text!a/b.html") == ("text", "a/b.html")
    assert split_plugin("plain/module") == (None, "plain/module")
