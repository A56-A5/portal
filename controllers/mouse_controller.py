"""
Mouse Controller - Handles mouse input and position control

On Wayland (especially Hyprland) pynput / xdotool inject via XTest, which
only reaches XWayland windows — native Wayland clients never see clicks /
scrolls.  For those we prefer:

  - position: hyprctl dispatch movecursor (Hyprland)
  - buttons / scroll: ydotool (writes /dev/uinput) or python-evdev UInput
  - fallback: xdotool / pynput (X11 only)
"""
import platform
import subprocess
import os
import json


class MouseController:
    def __init__(self):
        self.os_type = platform.system().lower()
        from pynput.mouse import Controller as PynputController, Button
        self._controller = PynputController()
        self.Button = Button

        self._win32api = None
        self.use_xdotool = False
        self.use_hyprctl = False
        self.use_ydotool = False
        self._uinput = None
        self._last_good_pos = (0, 0)

        if self.os_type == "windows":
            try:
                import win32api
                self._win32api = win32api
            except ImportError:
                pass
        elif self.os_type == "linux":
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

            # ydotool: Wayland-native injection via uinput
            try:
                res = subprocess.run(["which", "ydotool"], capture_output=True)
                if res.returncode == 0:
                    # Prefer socket presence (ydotoold running)
                    sock_ok = os.path.exists("/tmp/.ydotool_socket") or os.path.exists(
                        os.path.expanduser("~/.ydotool_socket")
                    )
                    self.use_ydotool = True
                    print(
                        "[Mouse] Using ydotool for click/scroll"
                        + (" (socket OK)" if sock_ok else " (start ydotoold if clicks fail)")
                    )
            except Exception:
                self.use_ydotool = False

            # python-evdev UInput for scroll (and buttons if ydotool missing)
            try:
                from evdev import UInput, ecodes
                self._uinput = UInput(
                    {
                        ecodes.EV_KEY: [
                            ecodes.BTN_LEFT,
                            ecodes.BTN_RIGHT,
                            ecodes.BTN_MIDDLE,
                        ],
                        ecodes.EV_REL: [
                            ecodes.REL_WHEEL,
                            ecodes.REL_HWHEEL,
                            ecodes.REL_X,
                            ecodes.REL_Y,
                        ],
                    },
                    name="portal-virtual-mouse",
                )
                print("[Mouse] evdev UInput ready for scroll/click fallback")
            except Exception:
                self._uinput = None

            try:
                res = subprocess.run(["which", "xdotool"], capture_output=True)
                self.use_xdotool = res.returncode == 0
            except Exception:
                self.use_xdotool = False

            if not self.use_hyprctl and self.use_xdotool:
                print("[Mouse] Using xdotool for cursor position")
            elif not self.use_hyprctl and not self.use_xdotool:
                print("[Mouse] WARNING: pynput-only position — edge detection may fail on Wayland")

    def _hypr_get_pos(self):
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

    def _hypr_set_pos(self, x, y):
        try:
            res = subprocess.run(
                ["hyprctl", "dispatch", "movecursor", str(int(x)), str(int(y))],
                capture_output=True, timeout=0.4
            )
            return res.returncode == 0
        except Exception:
            return False

    def _xdotool_get_pos(self):
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

    def get_display_size_matching_position(self):
        """Logical size matching cursorpos space (Hyprland scale-aware)."""
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
            m = next((x for x in monitors if x.get("focused")), monitors[0] if monitors else None)
            if not m:
                return None
            w = float(m.get("width", 0))
            h = float(m.get("height", 0))
            scale = float(m.get("scale", 1.0) or 1.0)
            if scale <= 0:
                scale = 1.0
            logical_w = int(round(w / scale))
            logical_h = int(round(h / scale))
            print(
                f"[Mouse] Hyprland monitor physical={int(w)}x{int(h)} scale={scale} "
                f"-> logical={logical_w}x{logical_h}"
            )
            return logical_w, logical_h
        except Exception:
            return None

    def get_display_size(self):
        size = self.get_display_size_matching_position()
        if size:
            return size
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
        return None

    @property
    def position(self):
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

    def _btn_name(self, button):
        name = getattr(button, "name", None) or str(button)
        name = name.lower().replace("button.", "")
        if "left" in name:
            return "left"
        if "right" in name:
            return "right"
        if "middle" in name:
            return "middle"
        return "left"

    def _ydotool_button(self, button, down: bool):
        """ydotool click uses bit flags; 0x40 left, 0x41 right, 0x42 middle.
        High bit 0x80 = release in some versions — use mousedown/mouseup if present.
        """
        name = self._btn_name(button)
        idx = {"left": 0, "right": 1, "middle": 2}.get(name, 0)
        # Try mousedown/mouseup first (clearer semantics)
        cmd_down = ["ydotool", "mousedown", str(idx)]
        cmd_up = ["ydotool", "mouseup", str(idx)]
        try:
            if down:
                r = subprocess.run(cmd_down, capture_output=True, timeout=0.5)
                if r.returncode == 0:
                    return True
            else:
                r = subprocess.run(cmd_up, capture_output=True, timeout=0.5)
                if r.returncode == 0:
                    return True
        except Exception:
            pass
        # Fallback: click with button codes (press+release only useful for click())
        code = {"left": "0xC0", "right": "0xC1", "middle": "0xC2"}.get(name, "0xC0")
        if not down:
            # release-only: many ydotool builds lack this; best-effort click skip
            return False
        try:
            subprocess.run(["ydotool", "click", code], capture_output=True, timeout=0.5)
            return True
        except Exception:
            return False

    def _uinput_button(self, button, down: bool):
        if not self._uinput:
            return False
        try:
            from evdev import ecodes
            name = self._btn_name(button)
            code = {
                "left": ecodes.BTN_LEFT,
                "right": ecodes.BTN_RIGHT,
                "middle": ecodes.BTN_MIDDLE,
            }.get(name, ecodes.BTN_LEFT)
            self._uinput.write(ecodes.EV_KEY, code, 1 if down else 0)
            self._uinput.syn()
            return True
        except Exception:
            return False

    def press(self, button):
        if self.os_type == "linux" and self.use_ydotool:
            if self._ydotool_button(button, True):
                return
        if self.os_type == "linux" and self._uinput:
            if self._uinput_button(button, True):
                return
        self._controller.press(button)

    def release(self, button):
        if self.os_type == "linux" and self.use_ydotool:
            if self._ydotool_button(button, False):
                return
        if self.os_type == "linux" and self._uinput:
            if self._uinput_button(button, False):
                return
        self._controller.release(button)

    def click(self, button):
        self.press(button)
        self.release(button)

    def scroll(self, dx, dy):
        if self.os_type == "linux" and self.use_ydotool:
            # ydotool mousemove --relative for wheel is not universal;
            # try `ydotool key` wheel isn't standard — use UInput if available
            pass
        if self.os_type == "linux" and self._uinput:
            try:
                from evdev import ecodes
                if dy:
                    self._uinput.write(ecodes.EV_REL, ecodes.REL_WHEEL, int(dy))
                if dx:
                    self._uinput.write(ecodes.EV_REL, ecodes.REL_HWHEEL, int(dx))
                self._uinput.syn()
                return
            except Exception:
                pass
        if self.os_type == "linux" and self.use_ydotool:
            # Approximate vertical scroll with repeated button 4/5 if needed — skip
            pass
        try:
            self._controller.scroll(dx, dy)
        except Exception:
            pass
