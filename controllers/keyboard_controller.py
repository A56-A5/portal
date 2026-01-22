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
        """Normalize key to a string representation"""
        # If it's already a pynput Key object, extract its name
        if isinstance(key, Key):
            return key.name  # Special keys like shift, ctrl, caps_lock
        # If it's a string, check if it's in "Key.xxx" format
        key_str = str(key)
        if key_str.startswith("Key."):
            return key_str.split(".", 1)[1].lower()
        return key_str.lower()  # Normalize to lowercase for consistency

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
        vk = self._key_to_vk(key_str)
        py_key = self._to_pynput_key(key_str)
        print(f"[KeyboardController][PRESS] key={key}, normalized={key_str}, vk={vk}, py_key={py_key}")
        if self.use_win32 and vk:
            self._win32_press(key_str)
        elif self.use_xdotool:
            self._xdotool_keydown(key_str)
        else:
            self._controller.press(py_key)

    def release(self, key):
        key_str = self._normalize_key(key)
        vk = self._key_to_vk(key_str)
        py_key = self._to_pynput_key(key_str)
        print(f"[KeyboardController][RELEASE] key={key}, normalized={key_str}, vk={vk}, py_key={py_key}")
        if self.use_win32 and vk:
            self._win32_release(key_str)
        elif self.use_xdotool:
            self._xdotool_keyup(key_str)
        else:
            self._controller.release(py_key)

    def tap(self, key):
        key_str = self._normalize_key(key)
        vk = self._key_to_vk(key_str)
        py_key = self._to_pynput_key(key_str)
        print(f"[KeyboardController][TAP] key={key}, normalized={key_str}, vk={vk}, py_key={py_key}")
        if self.use_win32 and vk:
            self._win32_tap(key_str)
        elif self.use_xdotool:
            self._xdotool_tap(key_str)
        else:
            self._controller.press(py_key)
            time.sleep(0.01)
            self._controller.release(py_key)

    def _to_pynput_key(self, key_str):
        """Convert normalized string to Key object if it's a special key"""
        # If it's already a Key object, return it
        if isinstance(key_str, Key):
            return key_str
        
        # Normalize to lowercase for lookup
        key_lower = key_str.lower() if isinstance(key_str, str) else str(key_str).lower()
        
        # Map of normalized key names to pynput Key objects
        special_keys = {
            "ctrl": Key.ctrl,
            "ctrl_l": Key.ctrl_l,
            "ctrl_r": Key.ctrl_r,
            "shift": Key.shift,
            "shift_l": Key.shift_l,
            "shift_r": Key.shift_r,
            "alt": Key.alt,
            "alt_l": Key.alt_l,
            "alt_r": Key.alt_r,
            "cmd": Key.cmd,
            "cmd_l": Key.cmd_l,
            "cmd_r": Key.cmd_r,
            "tab": Key.tab,
            "caps_lock": Key.caps_lock,
            "backspace": Key.backspace,
            "enter": Key.enter,
            "space": Key.space,
            "esc": Key.esc,
            "up": Key.up,
            "down": Key.down,
            "left": Key.left,
            "right": Key.right,
            "delete": Key.delete,
        }
        
        # Try to get the Key object from the mapping
        pynput_key = special_keys.get(key_lower)
        if pynput_key is not None:
            return pynput_key
        
        # If not found in special keys, it's either a regular character or invalid
        # For single characters, return as-is (pynput accepts char strings)
        # For anything else, try to get it as a Key attribute (handles edge cases)
        if len(key_lower) == 1:
            return key_str  # Single character, return original (preserve case for chars)
        
        # Try to get it as a Key attribute as a last resort
        try:
            return getattr(Key, key_lower)
        except AttributeError:
            # If all else fails, return the string and let pynput handle it (or error)
            return key_str

