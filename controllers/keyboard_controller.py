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
                self.use_win32 = False

        elif self.os_type == "linux":
            try:
                import subprocess
                self.subprocess = subprocess
                result = subprocess.run(["which", "xdotool"], capture_output=True)
                self.use_xdotool = result.returncode == 0
            except:
                self.use_xdotool = False

    def press(self, key):
        key_str = self._normalize_key(key)
        if self.use_win32 and len(key_str) == 1:
            self._win32_press(key_str)
        elif self.use_xdotool:
            self._xdotool_keydown(key_str)
        else:
            self._controller.press(key)

    def release(self, key):
        key_str = self._normalize_key(key)
        if self.use_win32 and len(key_str) == 1:
            self._win32_release(key_str)
        elif self.use_xdotool:
            self._xdotool_keyup(key_str)
        else:
            self._controller.release(key)

    def tap(self, key):
        key_str = self._normalize_key(key)
        if self.use_win32 and len(key_str) == 1:
            self._win32_tap(key_str)
        elif self.use_xdotool:
            self._xdotool_tap(key_str)
        else:
            self._controller.press(key)
            self._controller.release(key)

    def _normalize_key(self, key):
        from pynput.keyboard import Key as PKey
        if isinstance(key, PKey):
            return f"Key.{key.name}"
        return str(key)

    # -------- Linux xdotool methods --------
    def _xdotool_tap(self, key_str):
        xkey = self._key_to_xdotool(key_str)
        if len(xkey) == 1:
            self.subprocess.run(
                ["xdotool", "type", "--delay", "0", "--clearmodifiers", xkey],
                check=False
            )
        else:
            self.subprocess.run(["xdotool", "key", xkey], check=False)

    def _xdotool_keydown(self, key_str):
        xkey = self._key_to_xdotool(key_str)
        self.subprocess.run(["xdotool", "keydown", xkey], check=False)

    def _xdotool_keyup(self, key_str):
        xkey = self._key_to_xdotool(key_str)
        self.subprocess.run(["xdotool", "keyup", xkey], check=False)

    def _key_to_xdotool(self, key_str):
        key_map = {
            "Key.enter": "Return",
            "Key.tab": "Tab",
            "Key.space": "space",
            "Key.esc": "Escape",
            "Key.delete": "Delete",
            "Key.backspace": "BackSpace",
            "Key.ctrl": "Control_L",
            "Key.ctrl_l": "Control_L",
            "Key.ctrl_r": "Control_R",
            "Key.alt": "Alt_L",
            "Key.alt_l": "Alt_L",
            "Key.alt_r": "Alt_R",
            "Key.shift": "Shift_L",
            "Key.shift_l": "Shift_L",
            "Key.shift_r": "Shift_R",
            "Key.super": "Super_L",
            "Key.super_l": "Super_L",
            "Key.super_r": "Super_R",
            "ctrl": "Control_L",
            "alt": "Alt_L",
            "shift": "Shift_L",
        }
        return key_map.get(key_str, key_str)

    # -------- Windows win32api methods --------
    def _win32_tap(self, key_str):
        vk_and_shift = self.win32api.VkKeyScan(ord(key_str))
        if vk_and_shift == -1:
            ucode = ord(key_str)
            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", wintypes.WORD),
                    ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", wintypes.ULONG_PTR),
                ]
            class INPUT(ctypes.Structure):
                _fields_ = [("type", wintypes.DWORD), ("ki", KEYBDINPUT)]
            INPUT_KEYBOARD = 1
            KEYEVENTF_UNICODE = 0x0004
            KEYEVENTF_KEYUP = 0x0002
            press = INPUT(INPUT_KEYBOARD, KEYBDINPUT(0, ucode, KEYEVENTF_UNICODE, 0, 0))
            release = INPUT(INPUT_KEYBOARD, KEYBDINPUT(0, ucode, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0))
            ctypes.windll.user32.SendInput(1, ctypes.byref(press), ctypes.sizeof(press))
            time.sleep(0.01)
            ctypes.windll.user32.SendInput(1, ctypes.byref(release), ctypes.sizeof(release))
            return
        vk = vk_and_shift & 0xFF
        shift_state = (vk_and_shift >> 8) & 0xFF
        if shift_state & 0x01:
            self.win32api.keybd_event(0x10, 0, 0, 0)
        self.win32api.keybd_event(vk, 0, 0, 0)
        time.sleep(0.01)
        self.win32api.keybd_event(vk, 0, self.win32con.KEYEVENTF_KEYUP, 0)
        if shift_state & 0x01:
            self.win32api.keybd_event(0x10, 0, self.win32con.KEYEVENTF_KEYUP, 0)

    def _win32_press(self, key_str):
        vk = self._key_to_vk(key_str)
        if vk is not None:
            self.win32api.keybd_event(vk, 0, 0, 0)

    def _win32_release(self, key_str):
        vk = self._key_to_vk(key_str)
        if vk is not None:
            self.win32api.keybd_event(vk, 0, self.win32con.KEYEVENTF_KEYUP, 0)

    def _key_to_vk(self, key_str):
        key_map = {
            "enter": 0x0D,
            "tab": 0x09,
            "space": 0x20,
            "esc": 0x1B,
            "delete": 0x2E,
            "backspace": 0x08,
            "ctrl": 0x11,
            "alt": 0x12,
            "shift": 0x10,
            "up": 0x26,
            "down": 0x28,
            "left": 0x25,
            "right": 0x27,
        }
        return key_map.get(key_str.lower())

    # -------- Key parsing --------
    def parse_key(self, key_str):
        from pynput.keyboard import Key
        KEY_ALIAS = {
            "Key.ctrl": Key.ctrl_l,
            "Key.ctrl_l": Key.ctrl_l,
            "Key.ctrl_r": Key.ctrl_r,
            "Key.shift": Key.shift_l,
            "Key.shift_l": Key.shift_l,
            "Key.shift_r": Key.shift_r,
            "Key.alt": Key.alt_l,
            "Key.alt_l": Key.alt_l,
            "Key.alt_r": Key.alt_r,
            "Key.cmd": Key.cmd_l,
            "Key.cmd_l": Key.cmd_l,
            "Key.cmd_r": Key.cmd_r,
        }
        if key_str in KEY_ALIAS:
            return KEY_ALIAS[key_str]
        if key_str.startswith("Key."):
            return getattr(Key, key_str.split(".", 1)[1], None)
        return key_str
