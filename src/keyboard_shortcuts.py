from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class KeyboardShortcut:
    key: str
    label: str
    action: str
    shift: bool = False


SHORTCUTS: Tuple[KeyboardShortcut, ...] = (
    KeyboardShortcut("/", "Player search", "focus_player"),
    KeyboardShortcut("1", "Bid +$1", "click:+$1"),
    KeyboardShortcut("2", "Bid +$2", "click:+$2"),
    KeyboardShortcut("5", "Bid +$5", "click:+$5"),
    KeyboardShortcut("0", "Bid +$10", "click:+$10"),
    KeyboardShortcut("p", "Pass", "click:⏭️ PASS"),
    KeyboardShortcut("n", "Use top nomination", "click:🎯 USE TOP NOMINATION"),
    KeyboardShortcut("s", "Sale entry", "scroll:auction-sale-entry"),
    KeyboardShortcut("s", "Record prepared sale", "click:✅ RECORD SALE", shift=True),
    KeyboardShortcut(
        "r", "Refresh draft intelligence", "click:Refresh Draft Intelligence"
    ),
)


def shortcut_help() -> Tuple[str, ...]:
    return tuple(
        "{0}{1} — {2}".format(
            "Shift+" if shortcut.shift else "",
            shortcut.key.upper(),
            shortcut.label,
        )
        for shortcut in SHORTCUTS
    )


def build_shortcut_script() -> str:
    """Build parent-document shortcuts with a strict text-entry guard."""

    bindings = []
    for shortcut in SHORTCUTS:
        bindings.append(
            "{key:%r,shift:%s,action:%r}" % (
                shortcut.key,
                "true" if shortcut.shift else "false",
                shortcut.action,
            )
        )
    return """
<script>
(() => {
  const doc = window.parent.document;
  const win = window.parent;
  if (win.__auctionShortcutHandler) {
    doc.removeEventListener('keydown', win.__auctionShortcutHandler, true);
  }
  const bindings = [%s];
  const editable = (node) => node && (
    ['INPUT', 'TEXTAREA', 'SELECT'].includes(node.tagName) ||
    node.isContentEditable || node.closest('[contenteditable="true"]')
  );
  const clickButton = (text) => {
    const button = [...doc.querySelectorAll('button')]
      .find((node) => node.innerText.trim() === text);
    if (button && !button.disabled) { button.click(); return true; }
    return false;
  };
  const handler = (event) => {
    if (editable(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
    const binding = bindings.find((item) =>
      item.key === event.key.toLowerCase() && item.shift === event.shiftKey
    );
    if (!binding) return;
    let handled = false;
    if (binding.action === 'focus_player') {
      const box = [...doc.querySelectorAll('[data-testid="stSelectbox"]')]
        .find((node) => node.innerText.includes('Nominated Player'));
      const input = box && box.querySelector('input');
      if (input) { input.focus(); input.click(); handled = true; }
    } else if (binding.action.startsWith('click:')) {
      handled = clickButton(binding.action.slice(6));
    } else if (binding.action.startsWith('scroll:')) {
      const target = doc.getElementById(binding.action.slice(7));
      if (target) { target.scrollIntoView({behavior: 'smooth'}); handled = true; }
    }
    if (handled) { event.preventDefault(); event.stopPropagation(); }
  };
  win.__auctionShortcutHandler = handler;
  doc.addEventListener('keydown', handler, true);
})();
</script>
""" % ",".join(bindings)
