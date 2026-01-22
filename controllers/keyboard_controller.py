import platform
import time
import ctypes
from ctypes import wintypes
from pynput.keyboard import Controller as PynputKeyboardController, Key


class KeyboardController:
    def __init__(self):
        self._controller = PynputKeyboardController()
        self.os_type = platform.system().lower()

        self.win32api = None
        self.win32con = None
        self.use_win32 = False

        self.subprocess = None
        self.use_xdotool = False

        if self.os_type == "windows":
            try:
                import win32api
                import win32con
                self.win32api = win32api
                self.win32con = win32con
                self.use_win32 = True
            except ImportError:
                pass

        elif self.os_type == "linux":
            try:
                import subprocess
                self.subprocess = subprocess
                result = subprocess.run(
                    ["xdotool", "--version"],
                    stdout=self.subprocess.DEVNULL,
                    stderr=self.subprocess.DEVNULL,
                )
                self.use_xdotool = result.returncode == 0
            except Exception:
                pass

    def press(self, key):
        if self.use_xdotool:
            self._xdotool_keydown(key)
        elif self.use_win32:
            self._win32_press(key)
        else:
            self._controller.press(key)

    def release(self, key):
        if self.use_xdotool:
            self._xdotool_keyup(key)
        elif self.use_win32:
            self._win32_release(key)
        else:
            self._controller.release(key)

    def tap(self, key):
        if self.use_xdotool:
            self._xdotool_tap(key)
        elif self.use_win32:
            self._win32_tap(key)
        else:
            self._controller.press(key)
            self._controller.release(key)

    def _xdotool_keydown(self, key):
        xkey = self._key_to_xdotool(key)
        print(xkey)
        if xkey:
            self.subprocess.run(["xdotool", "keydown", xkey], check=False)

    def _xdotool_keyup(self, key):
        xkey = self._key_to_xdotool(key)
        if xkey:
            self.subprocess.run(["xdotool", "keyup", xkey], check=False)

    def _xdotool_tap(self, key):
        xkey = self._key_to_xdotool(key)

        # Normal characters
        if isinstance(key, str) and len(key) == 1:
            self.subprocess.run(
                ["xdotool", "type", "--delay", "0", "--clearmodifiers", key],
                check=False,
            )
            return

        # Special / modifier keys
        if xkey:
            self.subprocess.run(["xdotool", "key", xkey], check=False)

    def _key_to_xdotool(self, key):
        # pynput Key -> X11 keysym
        key_map = {
            Key.enter: "Return",
            Key.tab: "Tab",
            Key.space: "space",
            Key.esc: "Escape",
            Key.backspace: "BackSpace",
            Key.delete: "Delete",

            Key.shift: "Shift_L",
            Key.shift_l: "Shift_L",
            Key.shift_r: "Shift_R",

            Key.ctrl: "Control_L",
            Key.ctrl_l: "Control_L",
            Key.ctrl_r: "Control_R",

            Key.alt: "Alt_L",
            Key.alt_l: "Alt_L",
            Key.alt_r: "Alt_R",

            Key.cmd: "Super_L",
            Key.cmd_l: "Super_L",
            Key.cmd_r: "Super_R",

            Key.up: "Up",
            Key.down: "Down",
            Key.left: "Left",
            Key.right: "Right",
        }

        if isinstance(key, Key):
            return key_map.get(key)

        if isinstance(key, str):
            return key

        return None

    def _win32_tap(self, key):
        if isinstance(key, Key):
            key = self._key_to_vk(key)
            if key is None:
                return

        if isinstance(key, str) and len(key) == 1:
            vk_and_shift = self.win32api.VkKeyScan(ord(key))
            vk = vk_and_shift & 0xFF
        else:
            vk = self._key_to_vk(key)

        if vk is None:
            return

        self.win32api.keybd_event(vk, 0, 0, 0)
        time.sleep(0.01)
        self.win32api.keybd_event(vk, 0, self.win32con.KEYEVENTF_KEYUP, 0)

    def _win32_press(self, key):
        vk = self._key_to_vk(key)
        if vk:
            self.win32api.keybd_event(vk, 0, 0, 0)

    def _win32_release(self, key):
        vk = self._key_to_vk(key)
        if vk:
            self.win32api.keybd_event(vk, 0, self.win32con.KEYEVENTF_KEYUP, 0)

    def _key_to_vk(self, key):
        vk_map = {
            Key.enter: 0x0D,
            Key.tab: 0x09,
            Key.space: 0x20,
            Key.esc: 0x1B,
            Key.backspace: 0x08,
            Key.delete: 0x2E,

            Key.shift: 0x10,
            Key.ctrl: 0x11,
            Key.alt: 0x12,

            Key.up: 0x26,
            Key.down: 0x28,
            Key.left: 0x25,
            Key.right: 0x27,
        }

        if isinstance(key, Key):
            return vk_map.get(key)

        if isinstance(key, str) and len(key) == 1:
            return ord(key.upper())

        return None
