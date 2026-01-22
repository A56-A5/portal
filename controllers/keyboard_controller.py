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
    def _key_to_xdotool(self, key_str):
        """Convert pynput key name to xdotool key name"""
        # xdotool uses different key names than pynput
        xdotool_map = {
            "backspace": "BackSpace",
            "tab": "Tab",
            "caps_lock": "Caps_Lock",
            "cmd": "Super_L",  # Windows/Meta key
            "cmd_l": "Super_L",
            "cmd_r": "Super_R",
            "ctrl": "Control_L",
            "ctrl_l": "Control_L",
            "ctrl_r": "Control_R",
            "shift": "Shift_L",
            "shift_l": "Shift_L",
            "shift_r": "Shift_R",
            "alt": "Alt_L",
            "alt_l": "Alt_L",
            "alt_r": "Alt_R",
            "enter": "Return",
            "space": "space",
            "esc": "Escape",
            "delete": "Delete",
            "up": "Up",
            "down": "Down",
            "left": "Left",
            "right": "Right",
        }
        # Convert to lowercase for lookup
        key_lower = key_str.lower() if isinstance(key_str, str) else str(key_str).lower()
        # Return xdotool key name if mapped, otherwise return original (for regular characters)
        return xdotool_map.get(key_lower, key_str)

    def _xdotool_keydown(self, key_str):
        xdotool_key = self._key_to_xdotool(key_str)
        self.subprocess.run(["xdotool", "keydown", xdotool_key], check=False)

    def _xdotool_keyup(self, key_str):
        xdotool_key = self._key_to_xdotool(key_str)
        self.subprocess.run(["xdotool", "keyup", xdotool_key], check=False)

    def _xdotool_tap(self, key_str):
        xdotool_key = self._key_to_xdotool(key_str)
        self.subprocess.run(["xdotool", "key", xdotool_key], check=False)

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
        
        print(f"[KeyboardController][PRESS] key={key}, normalized={key_str}, vk={vk}, use_win32={self.use_win32}, use_xdotool={self.use_xdotool}")
        
        # On Windows, always prefer win32api if we have a VK mapping (most reliable)
        if self.os_type == "windows" and self.use_win32 and vk:
            self._win32_press(key_str)
            return
        
        # On Linux, prefer xdotool if available
        if self.use_xdotool:
            self._xdotool_keydown(key_str)
            return
        
        # Fall back to pynput Controller - ensure we have a valid Key object or single char
        try:
            py_key = self._to_pynput_key(key_str)
            self._controller.press(py_key)
        except (ValueError, AttributeError) as e:
            # If conversion fails, try win32api as last resort on Windows
            if self.os_type == "windows" and self.use_win32 and vk:
                print(f"[KeyboardController][PRESS] Pynput conversion failed, using win32api fallback: {e}")
                self._win32_press(key_str)
            else:
                print(f"[KeyboardController][PRESS] Error: Unable to press key '{key_str}': {e}")

    def release(self, key):
        key_str = self._normalize_key(key)
        vk = self._key_to_vk(key_str)
        
        print(f"[KeyboardController][RELEASE] key={key}, normalized={key_str}, vk={vk}, use_win32={self.use_win32}, use_xdotool={self.use_xdotool}")
        
        # On Windows, always prefer win32api if we have a VK mapping (most reliable)
        if self.os_type == "windows" and self.use_win32 and vk:
            self._win32_release(key_str)
            return
        
        # On Linux, prefer xdotool if available
        if self.use_xdotool:
            self._xdotool_keyup(key_str)
            return
        
        # Fall back to pynput Controller - ensure we have a valid Key object or single char
        try:
            py_key = self._to_pynput_key(key_str)
            self._controller.release(py_key)
        except (ValueError, AttributeError) as e:
            # If conversion fails, try win32api as last resort on Windows
            if self.os_type == "windows" and self.use_win32 and vk:
                print(f"[KeyboardController][RELEASE] Pynput conversion failed, using win32api fallback: {e}")
                self._win32_release(key_str)
            else:
                print(f"[KeyboardController][RELEASE] Error: Unable to release key '{key_str}': {e}")

    def tap(self, key):
        key_str = self._normalize_key(key)
        vk = self._key_to_vk(key_str)
        
        print(f"[KeyboardController][TAP] key={key}, normalized={key_str}, vk={vk}, use_win32={self.use_win32}, use_xdotool={self.use_xdotool}")
        
        # On Windows, always prefer win32api if we have a VK mapping (most reliable)
        if self.os_type == "windows" and self.use_win32 and vk:
            self._win32_tap(key_str)
            return
        
        # On Linux, prefer xdotool if available
        if self.use_xdotool:
            self._xdotool_tap(key_str)
            return
        
        # Fall back to pynput Controller - ensure we have a valid Key object or single char
        try:
            py_key = self._to_pynput_key(key_str)
            self._controller.press(py_key)
            time.sleep(0.01)
            self._controller.release(py_key)
        except (ValueError, AttributeError) as e:
            # If conversion fails, try win32api as last resort on Windows
            if self.os_type == "windows" and self.use_win32 and vk:
                print(f"[KeyboardController][TAP] Pynput conversion failed, using win32api fallback: {e}")
                self._win32_tap(key_str)
            else:
                print(f"[KeyboardController][TAP] Error: Unable to tap key '{key_str}': {e}")

    def _to_pynput_key(self, key_str):
        """Convert normalized string to Key object if it's a special key.
        Always returns a valid Key object for special keys, or a single character string for regular keys.
        Never returns a multi-character string that pynput can't recognize.
        """
        # If it's already a Key object, return it
        if isinstance(key_str, Key):
            return key_str
        
        # Normalize to lowercase for lookup
        if not isinstance(key_str, str):
            key_str = str(key_str)
        key_lower = key_str.lower()
        
        # Map of normalized key names to pynput Key objects
        # This MUST include all special keys we want to support
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
        
        # Try to get the Key object from the mapping first (most reliable)
        pynput_key = special_keys.get(key_lower)
        if pynput_key is not None:
            return pynput_key
        
        # For single characters, return as-is (pynput accepts char strings)
        if len(key_str) == 1:
            return key_str  # Single character, return original (preserve case for chars)
        
        # Try to get it as a Key attribute (handles edge cases and variations)
        # Try different case variations that pynput might use
        for variant in [key_lower, key_str, key_str.title(), key_str.upper()]:
            try:
                key_attr = getattr(Key, variant)
                if isinstance(key_attr, Key):
                    return key_attr
            except AttributeError:
                continue
        
        # If we still can't find it, try with underscore variations (e.g., "caps lock" -> "caps_lock")
        if " " in key_lower:
            try:
                key_attr = getattr(Key, key_lower.replace(" ", "_"))
                if isinstance(key_attr, Key):
                    return key_attr
            except AttributeError:
                pass
        
        # If we get here, it's a multi-character string that we couldn't convert to a Key object
        # This means it's either:
        # 1. A special key we don't have in our mapping (shouldn't happen for backspace, tab, etc.)
        # 2. An invalid key name
        # In this case, we should NOT return the string as pynput will reject it
        # Instead, we'll raise an error so the calling code can handle it (e.g., use win32api)
        raise ValueError(f"Unable to convert key '{key_str}' to pynput Key object. Key may not be supported.")

