"""
Theme detection and a small built-in dark ttk theme.

Tk/ttk do NOT automatically follow the OS/desktop theme the way native
GTK or Qt apps do - a stock Tkinter app renders in ttk's default light
theme regardless of whether the user has KDE Plasma, GNOME, or Windows
set to dark mode. That's a real, if longstanding, Tk limitation and this
module doesn't pretend to fully solve it (that would mean shipping/
depending on an external theme pack). What it does do:

  1. Best-effort detect whether the OS/DE is in dark mode.
  2. If so, apply a compact dark palette built on ttk's always-available
     'clam' base theme, so the app matches the user's system instead of
     always forcing light.

This also fixes the more clear-cut bug of a few widgets in main_window.py
using hardcoded fg='black'/'grey' colors that don't even follow *this*
app's own theme - those should use the styles defined here instead.
"""
import os
import platform
import subprocess


def detect_dark_mode() -> bool:
    """Best-effort OS/DE dark-mode detection. Returns False (light) on
    any platform/DE we can't confidently detect, rather than guessing."""
    system = platform.system().lower()
    try:
        if system == "windows":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0

        elif system == "linux":
            # GNOME / Cinnamon / most modern GTK-based desktops (including
            # GNOME-flavoured spins of other DEs) expose this directly.
            try:
                out = subprocess.run(
                    ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                    capture_output=True, text=True, timeout=1,
                )
                if "dark" in out.stdout.lower():
                    return True
            except Exception:
                pass

            # KDE Plasma: the active global color scheme name is recorded
            # in kdeglobals. Plasma's built-in dark schemes are all named
            # with "dark" in them (BreezeDark, etc.), which covers the
            # common case without needing a KDE-specific library.
            try:
                kdeglobals = os.path.expanduser("~/.config/kdeglobals")
                with open(kdeglobals) as f:
                    content = f.read().lower()
                if "colorscheme=" in content and "dark" in content:
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


# Compact palette - deliberately small; enough to keep the app legible in
# dark mode without trying to be a full theme engine.
DARK = {
    "bg": "#2b2b2b",
    "fg": "#e8e8e8",
    "muted_fg": "#9a9a9a",
    "entry_bg": "#3c3c3c",
    "select_bg": "#4a6fa5",
}


def apply_theme(root, style: "object", dark: bool):
    """Apply the dark palette on top of ttk's 'clam' theme, or leave the
    platform default (light) alone. Call once, right after the root
    window and a ttk.Style() are created."""
    if not dark:
        return

    style.theme_use("clam")
    bg, fg, entry_bg, select_bg = DARK["bg"], DARK["fg"], DARK["entry_bg"], DARK["select_bg"]

    root.configure(bg=bg)
    for widget in ("TFrame", "TLabelframe", "TLabelframe.Label", "TNotebook", "TCheckbutton", "TRadiobutton"):
        style.configure(widget, background=bg, foreground=fg)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("Muted.TLabel", background=bg, foreground=DARK["muted_fg"])
    style.configure("TButton", background=entry_bg, foreground=fg)
    style.map("TButton", background=[("active", select_bg)])
    style.configure("TEntry", fieldbackground=entry_bg, foreground=fg, insertcolor=fg)
    style.configure("Muted.TEntry", fieldbackground=entry_bg, foreground=DARK["muted_fg"], insertcolor=fg)
    style.configure("TNotebook.Tab", background=bg, foreground=fg)
    style.map("TNotebook.Tab", background=[("selected", entry_bg)], foreground=[("selected", fg)])

    # Toplevel popups (audio-IP prompt, hotkey recorder) are plain tk.Toplevel
    # windows, not ttk - give callers an easy way to match them.
    root.option_add("*Toplevel.background", bg)
    root.option_add("*Label.background", bg)
    root.option_add("*Label.foreground", fg)
    root.option_add("*Entry.background", entry_bg)
    root.option_add("*Entry.foreground", fg)
    root.option_add("*Entry.insertBackground", fg)
    root.option_add("*Button.background", entry_bg)
    root.option_add("*Button.foreground", fg)
