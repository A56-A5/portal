"""
Mouse Controller - Handles mouse input and position control

On Wayland (especially Hyprland) pynput / xdotool often cannot read or set
the global cursor position reliably.  We therefore prefer compositor-native
tools when available:

  - Hyprland:  hyprctl cursorpos  /  hyprctl dispatch movecursor
  - fallback:  xdotool getmouselocation / mousemove
  - last resort: pynput
"""
import platform
import subprocess
import os
import json


class MouseController:
    def __init__(self):
        self.os_type = platform.system().lower()
        from pynput.mouse import Controller as PynputController
        self._controller = PynputController()

        self._win32api = None
        self.use_xdotool = False
        self.use_hyprctl = False
        self._last_good_pos = (0, 0)

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
                        print("[Mouse] Using hyprctl for cursor position (Hyprland)")
                except Exception:
                    self.use_hyprctl = False

            try:
                res = subprocess.run(["which", "xdotool"], capture_output=True)
                self.use_xdotool = res.returncode == 0
            except Exception:
                self.use_xdotool = False

            if not self.use_hyprctl and self.use_xdotool:
                print("[Mouse] Using xdotool for cursor position")
            elif not self.use_hyprctl and not self.use_xdotool:
                print("[Mouse] WARNING: falling back to pynput only - edge detection may fail on Wayland")

    def _hypr_get_pos(self):
        """Return (x, y) from hyprctl cursorpos or None on failure."""
        try:
            res = subprocess.run(
                ["hyprctl", "cursorpos"],
                capture_output=True, text=True, timeout=0.4
            )
            if res.returncode == 0:
                text = res.stdout.strip().replace(",", " ")
                parts = text.split()
                if len(parts) >= 2:
                    return int(float(parts[0])), int(float(parts[1]))
        except Exception:
            pass
        return None

    def _xdotool_get_pos(self):
        """Return (x, y) from xdotool getmouselocation or None."""
        try:
            res = subprocess.run(
                ["xdotool", "getmouselocation", "--shell"],
                capture_output=True, text=True, timeout=0.4
            )
            if res.returncode == 0:
                x = y = None
                for line in res.stdout.splitlines():
                    if line.startswith("X="):
                        x = int(line.split("=", 1)[1])
                    elif line.startswith("Y="):
                        y = int(line.split("=", 1)[1])
                if x is not None and y is not None:
                    return x, y
        except Exception:
            pass
        return None

    def _hypr_set_pos(self, x, y):
        try:
            subprocess.run(
                ["hyprctl", "dispatch", "movecursor", str(int(x)), str(int(y))],
                capture_output=True, timeout=0.4, check=False
            )
            return True
        except Exception:
            return False

    def get_primary_size_hypr(self):
        """Return (width, height) of the focused monitor in the SAME space as cursorpos.

        Hyprland with fractional scaling (e.g. 1.5) reports physical width/height
        (1920x1080) but hyprctl cursorpos uses logical coordinates
        (1920/1.5 = 1280). Edge detection must use logical size or the right
        edge is unreachable and auto-hacks bounce forever.
        """
        if not self.use_hyprctl:
            return None
        try:
            res = subprocess.run(
                ["hyprctl", "monitors", "-j"],
                capture_output=True, text=True, timeout=1
            )
            if res.returncode != 0:
                return None
            monitors = json.loads(res.stdout)
            focused = None
            for m in monitors:
                if m.get("focused"):
                    focused = m
                    break
            m = focused or (monitors[0] if monitors else None)
            if not m:
                return None
            w = float(m.get("width", 0))
            h = float(m.get("height", 0))
            scale = float(m.get("scale", 1.0) or 1.0)
            if scale <= 0:
                scale = 1.0
            # Logical size = physical / scale (matches cursorpos under frac scale)
            logical_w = int(round(w / scale))
            logical_h = int(round(h / scale))
            print(f"[Mouse] Hyprland monitor physical={int(w)}x{int(h)} scale={scale} "
                  f"-> logical={logical_w}x{logical_h}")
            return logical_w, logical_h
        except Exception as e:
            print(f"[Mouse] hyprctl monitors failed: {e}")
        return None

    def get_display_size_matching_position(self):
        """Return (width, height) in the SAME coordinate space as .position.

        Order:
          1. Hyprland monitors (when hyprctl is used for position)
          2. xdotool getdisplaygeometry (when xdotool is used for position)
          3. xdpyinfo (X11 root)
          4. None  -> caller falls back to Qt/Tk
        """
        if self.use_hyprctl:
            size = self.get_primary_size_hypr()
            if size:
                return size

        if self.use_xdotool:
            try:
                res = subprocess.run(
                    ["xdotool", "getdisplaygeometry"],
                    capture_output=True, text=True, timeout=1
                )
                if res.returncode == 0:
                    parts = res.stdout.strip().split()
                    if len(parts) >= 2:
                        return int(parts[0]), int(parts[1])
            except Exception:
                pass

        # X11 root window size (matches pynput / XWayland coordinates)
        try:
            res = subprocess.run(
                ["xdpyinfo"],
                capture_output=True, text=True, timeout=1
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("dimensions:"):
                        # dimensions:    1280x720 pixels (....)
                        dim = line.split(":", 1)[1].strip().split()[0]
                        w, h = dim.lower().split("x")
                        return int(w), int(h)
        except Exception:
            pass

        return None

    @property
    def position(self):
        """Get current mouse position from the best available source."""
        if self.os_type == "linux" and self.use_hyprctl:
            pos = self._hypr_get_pos()
            if pos is not None:
                self._last_good_pos = pos
                return pos

        if self.os_type == "linux" and self.use_xdotool:
            pos = self._xdotool_get_pos()
            if pos is not None:
                self._last_good_pos = pos
                return pos

        try:
            pos = self._controller.position
            if pos:
                self._last_good_pos = pos
                return pos
        except Exception:
            pass

        return self._last_good_pos

    @position.setter
    def position(self, pos):
        """Set mouse position"""
        x, y = int(pos[0]), int(pos[1])

        if self.os_type == "windows" and self._win32api:
            try:
                self._win32api.SetCursorPos((x, y))
                self._last_good_pos = (x, y)
                return
            except Exception:
                pass

        if self.os_type == "linux" and self.use_hyprctl:
            if self._hypr_set_pos(x, y):
                self._last_good_pos = (x, y)
                return

        if self.os_type == "linux" and self.use_xdotool:
            try:
                subprocess.run(
                    ["xdotool", "mousemove", "--", str(x), str(y)],
                    check=False, timeout=0.4
                )
                self._last_good_pos = (x, y)
                return
            except Exception:
                pass

        try:
            self._controller.position = (x, y)
            self._last_good_pos = (x, y)
        except Exception:
            pass

    def press(self, button):
        self._controller.press(button)

    def release(self, button):
        self._controller.release(button)

    def click(self, button):
        self._controller.click(button)

    def scroll(self, dx, dy):
        self._controller.scroll(dx, dy)
