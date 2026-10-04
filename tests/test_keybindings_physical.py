import os

import pytest
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk


class FakeKeyEvent:
    """Minimal stand-in for a Gdk.EventKey used by Keybindings.lookup()."""

    def __init__(self, hardware_keycode, state, group=0, keyval=0):
        self.hardware_keycode = hardware_keycode
        self._state = state
        self.group = group
        self.keyval = keyval
        self.type = Gdk.EventType.KEY_PRESS

    def get_state(self):
        return self._state


@pytest.fixture
def keybindings():
    from terminatorlib.keybindings import Keybindings

    return Keybindings()


def test_physical_keybindings_default_is_disabled():
    """The physical keybinding lookup must be opt-in."""
    from terminatorlib import config

    assert config.DEFAULTS["global_config"]["physical_keybindings"] is False


def test_lookup_physical_resolves_by_keycode(keybindings):
    """
    With physical lookup enabled, a binding is matched by the hardware
    keycode even when the active layout reports a different keyval, which is
    what happens with non-Latin layouts such as Cyrillic.
    """
    keybindings.configure({"copy": "<Shift><Control>c"}, physical=True)

    # Physical keycode for the 'c' key on a standard layout. Shift is held,
    # so the binding is registered at level 1.
    event = FakeKeyEvent(
        54, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
    )

    assert keybindings.lookup(event) == "copy"


def test_physical_does_not_hijack_unshifted_keys(keybindings):
    """
    A shifted binding must not be triggered by the unshifted physical key.

    Otherwise Ctrl+C and Ctrl+D (which the terminal needs for SIGINT and
    EOF) would fire the Ctrl+Shift+C 'copy' and Ctrl+Shift+D 'detach_tab'
    bindings.
    """
    keybindings.configure(
        {"copy": "<Shift><Control>c", "detach_tab": "<Shift><Control>d"},
        physical=True,
    )
    ctrl = Gdk.ModifierType.CONTROL_MASK
    ctrl_shift = ctrl | Gdk.ModifierType.SHIFT_MASK

    # Unshifted Ctrl+C / Ctrl+D must not resolve to a Terminator action.
    assert keybindings.lookup(FakeKeyEvent(54, ctrl)) is None
    assert keybindings.lookup(FakeKeyEvent(40, ctrl)) is None

    # The shifted variants still work.
    assert keybindings.lookup(FakeKeyEvent(54, ctrl_shift)) == "copy"
    assert keybindings.lookup(FakeKeyEvent(40, ctrl_shift)) == "detach_tab"


def test_preferences_exposes_physical_keybindings_option():
    """The Global preferences tab must expose the opt-in checkbox."""
    glade = os.path.join(
        os.path.dirname(__file__), "..", "terminatorlib", "preferences.glade"
    )
    builder = Gtk.Builder()
    builder.add_from_file(os.path.abspath(glade))

    widget = builder.get_object("physical_keybindings")
    assert widget is not None
    assert "Physical keybindings" in widget.get_label()


def test_lookup_physical_disabled_falls_through(keybindings):
    """
    With physical lookup disabled (the default), no physical keycode map is
    built and the physical fallback never resolves an action.
    """
    keybindings.configure({"copy": "<Shift><Control>c"}, physical=False)

    assert keybindings._physical_lookup == {}
    assert (
        keybindings._lookup_physical(
            Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK, 54, 1
        )
        is None
    )
