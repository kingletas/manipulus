"""Pulling dependency names out of the four shapes an AMD module comes in."""

from manipulus.extract import dependency_names


def names(source: str) -> list[str]:
    return dependency_names(source.encode())[0]


def test_anonymous_define_with_a_dependency_list():
    assert names("define(['jquery', 'ko'], function ($, ko) {});") == ["jquery", "ko"]


def test_named_define_takes_its_second_argument():
    assert names("define('my/mod', ['jquery'], function ($) {});") == ["jquery"]


def test_define_with_no_dependencies_has_none():
    assert names("define(function () { return 1; });") == []


def test_inline_require_counts_as_a_dependency():
    assert names("define([], function () { require(['lazy/mod'], function () {}); });") == [
        "lazy/mod"
    ]


def test_a_computed_dependency_is_reported_rather_than_guessed():
    _, dynamic = dependency_names(b"define([modName], function () {});")
    assert dynamic


def test_comments_do_not_become_dependencies():
    assert names("define([/* a note */ 'real/mod'], function () {});") == ["real/mod"]


def test_both_quote_styles_work():
    assert names('define(["a/one", \'b/two\'], function () {});') == ["a/one", "b/two"]
