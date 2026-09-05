import platform
import time
from pynput.keyboard import Controller as PynputController, Key

class KeyboardController:
    def __init__(self):
        self._controller = PynputController()
        self.os_type = platform.system().lower()
        self.use_win32 = False
        self.use_xdotool = False
        self.use_ydotool = False
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
                import os as _os
                self.subprocess = subprocess
                # Prefer ydotool on Wayland (uinput); xdotool is XTest-only
                r = subprocess.run(["which", "ydotool"], capture_output=True)
                if r.returncode == 0:
                    self.use_ydotool = True
                    print("[Keyboard] ydotool available for key injection")
                result = subprocess.run(["which", "xdotool"], capture_output=True)
                self.use_xdotool = result.returncode == 0 and not self.use_ydotool
                if self.use_xdotool:
                    print("[Keyboard] Using xdotool (X11)")
            except Exception:
                pass
            # UInput virtual keyboard — works on Hyprland without ydotool
            self._kb_uinput = None
            try:
                from evdev import UInput, ecodes
                # Grab a wide KEY_* range for letters/modifiers
                keys = list(range(1, 128)) + [
                    125, 126,  # Super
                ]
                self._kb_uinput = UInput(
                    {ecodes.EV_KEY: keys},
                    name="portal-virtual-keyboard",
                )
                print("[Keyboard] evdev UInput virtual keyboard ready")
            except Exception as e:
                print(f"[Keyboard] UInput unavailable: {e}")
                self._kb_uinput = None

    def _normalize_key(self, key):
        """Normalize key to a string representation"""
        # If it's already a pynput Key object, extract its name
        if isinstance(key, Key):
            return key.name  # Special keys like shift, ctrl, caps_lock
        # If it's a string, check if it's in "Key.xxx" format
        key_str = str(key)
        if key_str.startswith("Key."):
            return key_str.split(".", 1)[1].lower()
        # For single characters, preserve case (important for special characters and their shift variants)
        if len(key_str) == 1:
            return key_str
        return key_str.lower()  # Normalize to lowercase for multi-character key names

    # ---------------- Linux ----------------
    def _key_to_xdotool(self, key_str):
        """Convert pynput key name or character to xdotool key name"""
        # xdotool uses different key names than pynput
        xdotool_map = {
            # Special keys
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
            # Special characters
            ",": "comma",
            ".": "period",
            "/": "slash",
            "'": "apostrophe",
            "[": "bracketleft",
            "]": "bracketright",
            "-": "minus",
            "=": "equal",
            "\\": "backslash",
            # Shift variants (xdotool handles these with shift modifier)
            "<": "comma",  # Will need shift
            ">": "period",  # Will need shift
            "?": "slash",  # Will need shift
            '"': "apostrophe",  # Will need shift
            "{": "bracketleft",  # Will need shift
            "}": "bracketright",  # Will need shift
            "_": "minus",  # Will need shift
            "+": "equal",  # Will need shift
            "|": "backslash",  # Will need shift
            "!": "exclam",  # or "1" with shift
            "@": "at",  # or "2" with shift
            "#": "numbersign",  # or "3" with shift
            "$": "dollar",  # or "4" with shift
            "%": "percent",  # or "5" with shift
            "^": "asciicircum",  # or "6" with shift
            "&": "ampersand",  # or "7" with shift
            "*": "asterisk",  # or "8" with shift
            "(": "parenleft",  # or "9" with shift
            ")": "parenright",  # or "0" with shift
            ":": "colon",  # or "semicolon" with shift
            ";": "semicolon",
            "`": "grave",
            "~": "asciitilde",
        }
        # For single characters, check the map directly (case-sensitive for characters)
        if len(key_str) == 1:
            return xdotool_map.get(key_str, key_str)
        # Convert to lowercase for lookup of special key names
        key_lower = key_str.lower() if isinstance(key_str, str) else str(key_str).lower()
        # Return xdotool key name if mapped, otherwise return original
        return xdotool_map.get(key_lower, key_str)

    def _needs_shift(self, key_str):
        """Check if a character needs shift modifier"""
        if len(key_str) != 1:
            return False
        shift_chars = "<>?\"{}_+|!@#$%^&*():~"
        return key_str in shift_chars

    def _xdotool_keydown(self, key_str):
        xdotool_key = self._key_to_xdotool(key_str)
        if self._needs_shift(key_str):
            # For shift characters, press shift first, then the base key
            base_key = self._key_to_xdotool(self._get_base_key(key_str))
            self.subprocess.run(["xdotool", "keydown", "shift_l"], check=False)
            self.subprocess.run(["xdotool", "keydown", base_key], check=False)
        else:
            self.subprocess.run(["xdotool", "keydown", xdotool_key], check=False)

    def _xdotool_keyup(self, key_str):
        xdotool_key = self._key_to_xdotool(key_str)
        if self._needs_shift(key_str):
            # For shift characters, release the base key first, then shift
            base_key = self._key_to_xdotool(self._get_base_key(key_str))
            self.subprocess.run(["xdotool", "keyup", base_key], check=False)
            self.subprocess.run(["xdotool", "keyup", "shift_l"], check=False)
        else:
            self.subprocess.run(["xdotool", "keyup", xdotool_key], check=False)

    def _xdotool_tap(self, key_str):
        xdotool_key = self._key_to_xdotool(key_str)
        if self._needs_shift(key_str):
            # For shift characters, use shift+key combination
            base_key = self._key_to_xdotool(self._get_base_key(key_str))
            self.subprocess.run(["xdotool", "key", f"shift_l+{base_key}"], check=False)
        else:
            self.subprocess.run(["xdotool", "key", xdotool_key], check=False)

    def _get_base_key(self, key_str):
        """Get the base key for a shift character (e.g., '<' -> ',', '!' -> '1')"""
        if len(key_str) != 1:
            return key_str
        shift_map = {
            "<": ",",
            ">": ".",
            "?": "/",
            '"': "'",
            "{": "[",
            "}": "]",
            "_": "-",
            "+": "=",
            "|": "\\",
            "!": "1",
            "@": "2",
            "#": "3",
            "$": "4",
            "%": "5",
            "^": "6",
            "&": "7",
            "*": "8",
            "(": "9",
            ")": "0",
            ":": ";",
            "~": "`",
        }
        return shift_map.get(key_str, key_str)

    # ---------------- Windows ----------------
    def _win32_press(self, key_str):
        # Handle shift characters
        if self._needs_shift(key_str):
            base_key = self._get_base_key(key_str)
            base_vk = self._key_to_vk(base_key)
            if base_vk:
                # Press shift
                self.win32api.keybd_event(0xA0, 0, 0, 0)  # VK_LSHIFT
                # Press base key
                self.win32api.keybd_event(base_vk, 0, 0, 0)
        else:
            vk = self._key_to_vk(key_str)
            if vk:
                self.win32api.keybd_event(vk, 0, 0, 0)

    def _win32_release(self, key_str):
        # Handle shift characters
        if self._needs_shift(key_str):
            base_key = self._get_base_key(key_str)
            base_vk = self._key_to_vk(base_key)
            if base_vk:
                # Release base key
                self.win32api.keybd_event(base_vk, 0, self.win32con.KEYEVENTF_KEYUP, 0)
                # Release shift
                self.win32api.keybd_event(0xA0, 0, self.win32con.KEYEVENTF_KEYUP, 0)  # VK_LSHIFT
        else:
            vk = self._key_to_vk(key_str)
            if vk:
                self.win32api.keybd_event(vk, 0, self.win32con.KEYEVENTF_KEYUP, 0)

    def _win32_tap(self, key_str):
        self._win32_press(key_str)
        time.sleep(0.01)
        self._win32_release(key_str)

    def _key_to_vk(self, key_str):
        """Full VK mapping for Windows special keys and characters"""
        vk_map = {
            # Special keys
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
            # Special characters (OEM keys)
            ",": 0xBC,  # VK_OEM_COMMA
            ".": 0xBE,  # VK_OEM_PERIOD
            "/": 0xBF,  # VK_OEM_2 (forward slash)
            "'": 0xDE,  # VK_OEM_7 (apostrophe)
            "[": 0xDB,  # VK_OEM_4 (left bracket)
            "]": 0xDD,  # VK_OEM_6 (right bracket)
            "-": 0xBD,  # VK_OEM_MINUS
            "=": 0xBB,  # VK_OEM_PLUS
            "\\": 0xDC,  # VK_OEM_5 (backslash)
            # Shift variants (same physical keys, but we handle shift separately)
            "<": 0xBC,  # Same as comma (shift+comma)
            ">": 0xBE,  # Same as period (shift+period)
            "?": 0xBF,  # Same as forward slash (shift+/)
            '"': 0xDE,  # Same as apostrophe (shift+')
            "{": 0xDB,  # Same as left bracket (shift+[)
            "}": 0xDD,  # Same as right bracket (shift+])
            "_": 0xBD,  # Same as minus (shift+-)
            "+": 0xBB,  # Same as equals (shift+=)
            "|": 0xDC,  # Same as backslash (shift+\)
            # Additional shift characters
            "!": 0x31,  # Same as 1 (shift+1)
            "@": 0x32,  # Same as 2 (shift+2)
            "#": 0x33,  # Same as 3 (shift+3)
            "$": 0x34,  # Same as 4 (shift+4)
            "%": 0x35,  # Same as 5 (shift+5)
            "^": 0x36,  # Same as 6 (shift+6)
            "&": 0x37,  # Same as 7 (shift+7)
            "*": 0x38,  # Same as 8 (shift+8)
            "(": 0x39,  # Same as 9 (shift+9)
            ")": 0x30,  # Same as 0 (shift+0)
            ":": 0xBA,  # VK_OEM_1 (semicolon, shift+;)
            ";": 0xBA,  # VK_OEM_1 (semicolon)
            "`": 0xC0,  # VK_OEM_3 (grave accent)
            "~": 0xC0,  # VK_OEM_3 (grave accent, shift+`)
        }
        return vk_map.get(key_str, None)

    # ---------------- Public API ----------------

    # Linux KEY_* numeric codes, keyed by the same lowercase name strings
    # _normalize_key()/_keycode() produce. This mirrors the two lookup
    # tables in network/share_manager.py's evdev reader (KEYMAP + US),
    # just inverted (name -> code instead of code -> name), so capture
    # and injection always agree on what a given code means. If you add
    # a new key there, add it here too.
    _KEYCODE_MAP = {
        # Special keys (from share_manager.py's KEYMAP)
        "esc": 1, "backspace": 14, "tab": 15, "enter": 28,
        "ctrl": 29, "ctrl_l": 29, "shift": 42, "shift_l": 42, "shift_r": 54,
        "alt": 56, "alt_l": 56, "ctrl_r": 97, "alt_r": 100,
        "cmd": 125, "cmd_r": 126,
        "space": 57, "delete": 111,
        "up": 103, "down": 108, "left": 105, "right": 106,
        "home": 102, "end": 107, "page_up": 104, "page_down": 109,
        # Printable US layout (from share_manager.py's US map)
        "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
        "-": 12, "=": 13, "q": 16, "w": 17, "e": 18, "r": 19, "t": 20, "y": 21, "u": 22,
        "i": 23, "o": 24, "p": 25, "[": 26, "]": 27, "a": 30, "s": 31, "d": 32, "f": 33,
        "g": 34, "h": 35, "j": 36, "k": 37, "l": 38, ";": 39, "'": 40, "`": 41,
        "\\": 43, "z": 44, "x": 45, "c": 46, "v": 47, "b": 48, "n": 49, "m": 50,
        ",": 51, ".": 52, "/": 53,
    }

    def _keycode(self, key_str):
        s = str(key_str)
        if s.startswith("Key."):
            s = s.split(".", 1)[1]
        s = s.lower()
        return self._KEYCODE_MAP.get(s)

    def _ydotool_key(self, key_str, down: bool):
        code = self._keycode(key_str)
        if code is None:
            return False
        try:
            self.subprocess.run(
                ["ydotool", "key", f"{code}:{1 if down else 0}"],
                capture_output=True, timeout=2,
            )
            return True
        except Exception:
            return False

    def _uinput_key(self, key_str, down: bool):
        ui = getattr(self, "_kb_uinput", None)
        if ui is None:
            return False
        try:
            code = self._keycode(key_str)
            if code is None:
                return False
            from evdev import ecodes
            ui.write(ecodes.EV_KEY, code, 1 if down else 0)
            ui.syn()
            return True
        except Exception:
            return False

    def press(self, key):
        key_str = self._normalize_key(key)
        vk = self._key_to_vk(key_str)
        
        # On Windows, always prefer win32api if we have a VK mapping (most reliable)
        if self.os_type == "windows" and self.use_win32 and vk:
            self._win32_press(key_str)
            return
        
        # Wayland: UInput / ydotool before xdotool/XTest
        if self._uinput_key(key_str, True):
            return
        if getattr(self, "use_ydotool", False) and self._ydotool_key(key_str, True):
            return

        if self.use_xdotool:
            self._xdotool_keydown(key_str)
            return
        
        try:
            py_key = self._to_pynput_key(key_str)
            self._controller.press(py_key)
        except (ValueError, AttributeError) as e:
            if self.os_type == "windows" and self.use_win32 and vk:
                print(f"[KeyboardController][PRESS] Pynput conversion failed, using win32api fallback: {e}")
                self._win32_press(key_str)
            else:
                print(f"[KeyboardController][PRESS] Error: Unable to press key '{key_str}': {e}")

    def release(self, key):
        key_str = self._normalize_key(key)
        vk = self._key_to_vk(key_str)
        
        # On Windows, always prefer win32api if we have a VK mapping (most reliable)
        if self.os_type == "windows" and self.use_win32 and vk:
            self._win32_release(key_str)
            return
        
        if self._uinput_key(key_str, False):
            return
        if getattr(self, "use_ydotool", False) and self._ydotool_key(key_str, False):
            return

        if self.use_xdotool:
            self._xdotool_keyup(key_str)
            return
        
        try:
            py_key = self._to_pynput_key(key_str)
            self._controller.release(py_key)
        except (ValueError, AttributeError) as e:
            if self.os_type == "windows" and self.use_win32 and vk:
                print(f"[KeyboardController][RELEASE] Pynput conversion failed, using win32api fallback: {e}")
                self._win32_release(key_str)
            else:
                print(f"[KeyboardController][RELEASE] Error: Unable to release key '{key_str}': {e}")

    def tap(self, key):
        key_str = self._normalize_key(key)
        vk = self._key_to_vk(key_str)
        
        # On Windows, always prefer win32api if we have a VK mapping (most reliable)
        if self.os_type == "windows" and self.use_win32 and vk:
            self._win32_tap(key_str)
            return
        
        if self._uinput_key(key_str, True):
            self._uinput_key(key_str, False)
            return
        if getattr(self, "use_ydotool", False):
            if self._ydotool_key(key_str, True) and self._ydotool_key(key_str, False):
                return

        if self.use_xdotool:
            self._xdotool_tap(key_str)
            return
        
        try:
            py_key = self._to_pynput_key(key_str)
            self._controller.press(py_key)
            time.sleep(0.01)
            self._controller.release(py_key)
        except (ValueError, AttributeError) as e:
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

