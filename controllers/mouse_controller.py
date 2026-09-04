"""
Mouse Controller - Handles mouse input and position control

On Wayland (especially Hyprland) pynput / xdotool often cannot read or set
the global cursor position reliably.  We therefore prefer compositor-native
tools when available:

  - Hyprland:  hyprctl cursorpos  /  hyprctl dispatch movecursor
  - fallback:  xdotool (X11 / XWayland)
  - last resort: pynput
"""
import platform
import subprocess
import os


class MouseController:
    def __init__(self):
        self.os_type = platform.system().lower()
        from pynput.mouse import Controller as PynputController
        self._controller = PynputController()

        self._win32api = None
        self.use_xdotool = False
        self.use_hyprctl = False

        if self.os_type == "windows":
            try:
                import win32api
                self._win32api = win32api
            except ImportError:
                pass
        elif self.os_type == "linux":
            # Prefer Hyprland native cursor control when running under Hyprland
            if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
                try:
                    res = subprocess.run(
                        ["hyprctl", "cursorpos"],
                        capture_output=True, text=True, timeout=1
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        self.use_hyprctl = True
                except Exception:
                    self.use_hyprctl = False

            if not self.use_hyprctl:
                try:
                    res = subprocess.run(["which", "xdotool"], capture_output=True)
                    self.use_xdotool = res.returncode == 0
                except Exception:
                    self.use_xdotool = False

    def _hypr_get_pos(self):
        """Return (x, y) from hyprctl cursorpos or None on failure."""
        try:
            res = subprocess.run(
                ["hyprctl", "cursorpos"],
                capture_output=True, text=True, timeout=0.5
            )
            if res.returncode == 0:
                # Output is typically "1234, 567" or "1234 567"
                text = res.stdout.strip().replace(",", " ")
                parts = text.split()
                if len(parts) >= 2:
                    return int(float(parts[0])), int(float(parts[1]))
        except Exception:
            pass
        return None

    def _hypr_set_pos(self, x, y):
        try:
            subprocess.run(
                ["hyprctl", "dispatch", "movecursor", str(int(x)), str(int(y))],
                capture_output=True, timeout=0.5, check=False
            )
            return True
        except Exception:
            return False

    @property
    def position(self):
        """Get current mouse position"""
        if self.os_type == "linux" and self.use_hyprctl:
            pos = self._hypr_get_pos()
            if pos is not None:
                return pos
        # Fallback (works on X11 and often on XWayland)
        return self._controller.position

    @position.setter
    def position(self, pos):
        """Set mouse position"""
        x, y = int(pos[0]), int(pos[1])

        if self.os_type == "windows" and self._win32api:
            try:
                self._win32api.SetCursorPos((x, y))
                return
            except Exception:
                pass

        if self.os_type == "linux" and self.use_hyprctl:
            if self._hypr_set_pos(x, y):
                return

        if self.os_type == "linux" and self.use_xdotool:
            try:
                subprocess.run(
                    ["xdotool", "mousemove", str(x), str(y)],
                    check=False, timeout=0.5
                )
                return
            except Exception:
                pass

        # Last resort
        try:
            self._controller.position = (x, y)
        except Exception:
            pass

    def press(self, button):
        """Press mouse button"""
        self._controller.press(button)

    def release(self, button):
        """Release mouse button"""
        self._controller.release(button)

    def click(self, button):
        """Click mouse button"""
        self._controller.click(button)

    def scroll(self, dx, dy):
        """Scroll mouse"""
        self._controller.scroll(dx, dy)
