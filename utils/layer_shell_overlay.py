"""
wlr-layer-shell overlay for Hyprland / wlroots compositors.

Ordinary XWayland/Qt toplevels cannot stack above layer-shell surfaces
(waybar, etc.). This module creates a real GtkLayerShell surface on the
OVERLAY layer so Portal does not need to SIGUSR1-toggle waybar on each
input transition.

Requires: gtk3, python-gobject, gtk-layer-shell
  Arch: sudo pacman -S gtk-layer-shell python-gobject gtk3
"""
from __future__ import annotations

import logging
import os
import sys

_log = logging.getLogger(__name__)

_GTK_OK = None  # None=untested, True/False after probe


def layer_shell_available() -> bool:
    """True if Gtk + GtkLayerShell typelibs import cleanly."""
    global _GTK_OK
    if _GTK_OK is not None:
        return _GTK_OK
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") and not os.environ.get("SWAYSOCK"):
        # Still allow probe — useful on other wlroots compositors
        pass
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import Gtk, GtkLayerShell  # noqa: F401
        _GTK_OK = True
    except Exception as e:
        _log.info("[Overlay] layer-shell unavailable: %s", e)
        _GTK_OK = False
    return _GTK_OK


class LayerShellOverlay:
    """Transparent fullscreen overlay on the compositor OVERLAY layer."""

    def __init__(self):
        self.win = None
        self._pump_timer = None  # Qt QTimer if hosted inside QApplication

    def create(self, opaque_test: bool = False):
        """Map a fullscreen layer-shell surface.

        opaque_test=True uses a visible red tint (debug only).
        Production uses fully transparent background.
        """
        if not layer_shell_available():
            raise RuntimeError("gtk-layer-shell not available")

        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import Gtk, Gdk
        from gi.repository import GtkLayerShell as LayerShell

        # One display connection for the process
        if not Gtk.init_check(sys.argv[:1])[0]:
            raise RuntimeError("Gtk.init_check failed")

        win = Gtk.Window(title="portal-overlay")
        LayerShell.init_for_window(win)
        LayerShell.set_layer(win, LayerShell.Layer.OVERLAY)
        LayerShell.set_exclusive_zone(win, -1)
        for edge in (
            LayerShell.Edge.TOP,
            LayerShell.Edge.BOTTOM,
            LayerShell.Edge.LEFT,
            LayerShell.Edge.RIGHT,
        ):
            LayerShell.set_anchor(win, edge, True)
        # ON_DEMAND: do not steal compositor shortcuts (Super+key, etc.)
        LayerShell.set_keyboard_mode(win, LayerShell.KeyboardMode.ON_DEMAND)

        win.set_app_paintable(True)
        screen = win.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            win.set_visual(visual)

        css = Gtk.CssProvider()
        if opaque_test:
            css.load_from_data(
                b"window { background-color: rgba(200, 30, 30, 0.35); }"
            )
        else:
            # Fully transparent — covers waybar without hiding it
            css.load_from_data(
                b"window { background-color: rgba(0, 0, 0, 0.01); }"
            )
        Gtk.StyleContext.add_provider_for_screen(
            screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Blank cursor while sharing
        try:
            win.get_window()  # may be None before realize
        except Exception:
            pass
        win.connect(
            "realize",
            lambda w: w.get_window().set_cursor(
                Gdk.Cursor.new_from_name(w.get_display(), "none")
            )
            if w.get_window()
            else None,
        )

        win.show_all()
        self.win = win
        _log.info("[Overlay] layer-shell CREATED (OVERLAY layer, waybar stays)")
        print("[Overlay] layer-shell CREATED (covers waybar, no toggle)")

    def destroy(self):
        if self._pump_timer is not None:
            try:
                self._pump_timer.stop()
            except Exception:
                pass
            self._pump_timer = None
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass
            self.win = None
            _log.info("[Overlay] layer-shell DESTROYED")
            print("[Overlay] layer-shell DESTROYED")
        # Drain any pending destroy events
        self.pump()

    def pump(self):
        """Process pending GTK events (call from Qt timer / main thread)."""
        if not layer_shell_available():
            return
        try:
            from gi.repository import Gtk
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
        except Exception:
            pass

    def start_qt_pump(self, qtimer_cls, interval_ms: int = 16):
        """Attach a Qt QTimer that pumps GTK so the surface stays responsive."""
        if self._pump_timer is not None:
            return
        timer = qtimer_cls()
        timer.setInterval(interval_ms)
        timer.timeout.connect(self.pump)
        timer.start()
        self._pump_timer = timer
