"""Harvesting entry points from rendered HTML and from layout XML."""

from manipulus import entrypoints

# The shape Magento renders: a selector, a component, and a jsLayout tree beneath it.
PAGE = """
<html><body>
<div data-mage-init='{"Magento_Catalog/js/product-gallery": {"mode": "full"}}'></div>
<script type="text/x-magento-init">
{
    "*": {
        "Magento_Ui/js/core/app": {
            "components": {
                "checkout": {
                    "component": "uiComponent",
                    "children": {
                        "steps": { "component": "Magento_Checkout/js/view/progress-bar" }
                    }
                }
            }
        }
    }
}
</script>
<script type="text/x-magento-init">
{"#product_addtocart_form": {"priceOptions": {"controlContainer": ".field"}}}
</script>
</body></html>
"""


def test_component_keys_under_a_selector_are_found():
    found = entrypoints.from_html(PAGE, "product", "https://store.test/p.html")
    assert "Magento_Ui/js/core/app" in found.names
    assert "priceOptions" in found.names


def test_data_mage_init_attributes_are_found():
    found = entrypoints.from_html(PAGE, "product", "https://store.test/p.html")
    assert "Magento_Catalog/js/product-gallery" in found.names


def test_nested_jslayout_components_are_found():
    """This tree only exists in rendered HTML, which is why the HTTP layer earns its keep."""
    found = entrypoints.from_html(PAGE, "product", "https://store.test/p.html")
    assert "Magento_Checkout/js/view/progress-bar" in found.names
    assert "uiComponent" in found.names


def test_a_selector_is_never_mistaken_for_a_component():
    found = entrypoints.from_html(PAGE, "product", "https://store.test/p.html")
    assert "#product_addtocart_form" not in found.names
    assert not any(name.startswith((".", "#")) for name in found.names)


def test_malformed_json_is_skipped_not_fatal():
    found = entrypoints.from_html(
        '<script type="text/x-magento-init">{not json}</script>', "cms", "x"
    )
    assert found.names == set()


def test_where_each_name_came_from_is_recorded():
    found = entrypoints.from_html(PAGE, "product", "https://store.test/p.html")
    assert found.detail["Magento_Ui/js/core/app"] == "https://store.test/p.html"


def test_components_are_read_out_of_layout_xml(tmp_path):
    layout = tmp_path / "checkout_index_index.xml"
    layout.write_text(
        '<?xml version="1.0"?><page><body><referenceBlock name="checkout.root">'
        '<arguments><argument name="jsLayout" xsi:type="array" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<item name="components" xsi:type="array"><item name="checkout" xsi:type="array">'
        '<item name="component" xsi:type="string">Magento_Checkout/js/view/onepage</item>'
        "</item></item></argument></arguments></referenceBlock></body></page>"
    )
    assert entrypoints.components_in_layout(layout) == {"Magento_Checkout/js/view/onepage"}
