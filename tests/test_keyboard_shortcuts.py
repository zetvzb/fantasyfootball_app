from src.keyboard_shortcuts import SHORTCUTS, build_shortcut_script, shortcut_help


def test_shortcuts_cover_required_live_actions():
    actions = {shortcut.action for shortcut in SHORTCUTS}
    assert "focus_player" in actions
    assert {"click:+$1", "click:+$2", "click:+$5", "click:+$10"} <= actions
    assert "click:⏭️ PASS" in actions
    assert "click:✅ RECORD SALE" in actions
    assert "click:Refresh Draft Intelligence" in actions
    assert "click:🎯 USE TOP NOMINATION" in actions


def test_script_ignores_text_entry_and_modifier_combinations():
    script = build_shortcut_script()
    assert "INPUT', 'TEXTAREA', 'SELECT" in script
    assert "node.isContentEditable" in script
    assert "event.ctrlKey || event.metaKey || event.altKey" in script
    assert "preventDefault" in script
    assert any("Shift+S" in line for line in shortcut_help())


def test_draft_mode_import_resolves_with_shortcut_component():
    from src.views.draft_mode import render_draft_mode_view
    assert callable(render_draft_mode_view)
