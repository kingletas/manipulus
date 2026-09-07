"""Reading deployed CSS, and the limits of judging it by class name."""

from manipulus import stylesheets

SHEET = """
/* a comment { not a rule } */
.header, .footer { color: red; }
@media (min-width: 768px) {
    .desktop-only { display: block; }
}
a:hover { text-decoration: underline; }
.empty {}
"""


def test_rules_inside_media_queries_are_counted(tmp_path):
    assert stylesheets.count_rules(SHEET) == 3


def test_an_empty_rule_is_not_counted():
    assert stylesheets.count_rules(".a {}") == 0


def test_a_comment_is_not_mistaken_for_a_rule():
    assert stylesheets.count_rules("/* .fake { a: b } */") == 0


def test_class_names_are_collected_including_inside_media_queries():
    assert stylesheets.classes_in(SHEET) == {"header", "footer", "desktop-only", "empty"}


def test_classes_on_a_page_are_read_from_class_attributes():
    html = '<div class="header nav"><span class=\'footer\'></span></div>'
    assert stylesheets.classes_on_page(html) == {"header", "nav", "footer"}


def test_linked_stylesheets_are_found():
    html = '<link rel="stylesheet" href="/static/css/styles-m.css?v=1"><link href="x.css">'
    assert stylesheets.linked_stylesheets(html) == ["/static/css/styles-m.css?v=1", "x.css"]


def test_a_theme_is_read_from_disk(tmp_path):
    (tmp_path / "css").mkdir()
    (tmp_path / "css" / "a.css").write_text(".one { color: red; }")
    sheets = stylesheets.read_theme(tmp_path)
    assert [s.relative for s in sheets] == ["css/a.css"]
    assert sheets[0].rule_count == 1


def test_coverage_is_a_floor_not_a_verdict(tmp_path):
    """A class JavaScript adds after load is invisible here, which is why it is a floor."""
    (tmp_path / "a.css").write_text(".present { a: b; } .added-by-js { c: d; }")
    sheets = stylesheets.read_theme(tmp_path)
    rows = stylesheets.coverage(sheets, '<div class="present"></div>')
    assert rows[0].classes_in_css == 2
    assert rows[0].classes_present == 1
    assert rows[0].percent == 50.0
