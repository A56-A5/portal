import platform
import time
from pynput.keyboard import Controller as PynputController, Key

class KeyboardController:
    def __init__(self):
        self._controller = PynputController()
        self.os_type = platform.system().lower()
        self.use_win32 = False
        self.use_xdotool = False
        self.subprocess = None

        if self.os_type == "windows":
            try:
                import win32api, win32con
                self.win32api = win32api
                self.win32con = win32con
                self.use_win32 = True
            except ImportError:
                pass
        elif self.os_type == "linux":
            try:
                import subprocess
                self.subprocess = subprocess
                result = subprocess.run(["which", "xdotool"], capture_output=True)
                self.use_xdotool = result.returncode == 0
            except:
                pass

    def _normalize_key(self, key):
        if hasattr(key, "name"):
            return key.name  # Special keys like shift, ctrl, caps_lock
        return str(key)      # Normal keys like 'a', '1'

    # ---------------- Linux ----------------
    def _xdotool_keydown(self, key_str):
        self.subprocess.run(["xdotool", "keydown", key_str], check=False)

    def _xdotool_keyup(self, key_str):
        self.subprocess.run(["xdotool", "keyup", key_str], check=False)

    def _xdotool_tap(self, key_str):
        self.subprocess.run(["xdotool", "key", key_str], check=False)

    # ---------------- Windows ----------------
    def _win32_press(self, key_str):
        vk = self._key_to_vk(key_str)
        if vk:
            self.win32api.keybd_event(vk, 0, 0, 0)

    def _win32_release(self, key_str):
        vk = self._key_to_vk(key_str)
        if vk:
            self.win32api.keybd_event(vk, 0, self.win32con.KEYEVENTF_KEYUP, 0)

    def _win32_tap(self, key_str):
        self._win32_press(key_str)
        time.sleep(0.01)
        self._win32_release(key_str)

    def _key_to_vk(self, key_str):
        """Full VK mapping for Windows special keys"""
        vk_map = {
            "enter": 0x0D,
            "tab": 0x09,
            "space": 0x20,
            "esc": 0x1B,
            "backspace": 0x08,
            "delete": 0x2E,
            "caps_lock": 0x14,
            "ctrl": 0x11,
            "ctrl_l": 0xA2,
            "ctrl_r": 0xA3,
            "alt": 0x12,
            "alt_l": 0x12,
            "alt_r": 0xA5,
            "shift": 0x10,
            "shift_l": 0xA0,
            "shift_r": 0xA1,
            "cmd": 0x5B,  # Left Windows key
            "up": 0x26,
            "down": 0x28,
            "left": 0x25,
            "right": 0x27,
        }
        return vk_map.get(key_str.lower(), None)

    # ---------------- Public API ----------------
    def press(self, key):
        key_str = self._normalize_key(key)
        if self.use_win32 and self._key_to_vk(key_str):
            self._win32_press(key_str)
        elif self.use_xdotool:
            self._xdotool_keydown(key_str)
        else:
            self._controller.press(key)

    def release(self, key):
        key_str = self._normalize_key(key)
        if self.use_win32 and self._key_to_vk(key_str):
            self._win32_release(key_str)
        elif self.use_xdotool:
            self._xdotool_keyup(key_str)
        else:
            self._controller.release(key)

    def tap(self, key):
        key_str = self._normalize_key(key)
        if self.use_win32 and self._key_to_vk(key_str):
            self._win32_tap(key_str)
        elif self.use_xdotool:
            self._xdotool_tap(key_str)
        else:
            self._controller.press(key)
            time.sleep(0.01)
            self._controller.release(key)
