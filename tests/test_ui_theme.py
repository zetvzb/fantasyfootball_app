from src.ui_theme import build_global_css


def test_global_css_contains_product_shell_and_responsive_rules():
    css = build_global_css()

    assert css.startswith("\n<style>")
    assert ".copilot-page-header" in css
    assert ".copilot-brand" in css
    assert "@media (max-width: 900px)" in css
    assert "prefers-reduced-motion" in css
    assert css.endswith("</style>\n")


def test_global_css_is_fully_formatted():
    css = build_global_css()

    assert "{accent}" not in css
    assert "{surface}" not in css
    assert "#6C6CF5" in css
