"""
Keyboard Controller - Handles keyboard input control
Uses win32api on Windows for better compatibility in secure contexts (lockscreen, password fields)
"""
import platform
from pynput.keyboard import Controller as PynputKeyboardController, Key

class KeyboardController:
    def __init__(self):
        self._controller = PynputKeyboardController()
        self.os_type = platform.system().lower()
        
        # Use win32api for Windows (more reliable in secure contexts)
        if self.os_type == "windows":
            try:
                import win32api
                import win32con
                self.win32api = win32api
                self.win32con = win32con
                self.use_win32 = True
            except ImportError:
                self.use_win32 = False
        else:
            self.use_win32 = False
    
    def press(self, key):
        """Press a key"""
        if self.use_win32 and isinstance(key, str):
            self._win32_press(key)
        else:
            self._controller.press(key)
    
    def release(self, key):
        """Release a key"""
        if self.use_win32 and isinstance(key, str):
            self._win32_release(key)
        else:
            self._controller.release(key)
    
    def _win32_press(self, key_str):
        """Press key using win32api for better system-level support"""
        try:
            vk = self._key_to_vk(key_str)
            if vk:
                self.win32api.keybd_event(vk, 0, 0, 0)
        except Exception as e:
            print(f"[Keyboard] Win32 press error: {e}")
    
    def _win32_release(self, key_str):
        """Release key using win32api"""
        try:
            vk = self._key_to_vk(key_str)
            if vk:
                self.win32api.keybd_event(vk, 0, self.win32con.KEYEVENTF_KEYUP, 0)
        except Exception as e:
            print(f"[Keyboard] Win32 release error: {e}")
    
    def _key_to_vk(self, key_str):
        """Convert key string to Windows virtual key code"""
        # Handle special keys
        key_map = {
            'enter': 0x0D, 'tab': 0x09, 'space': 0x20, 'esc': 0x1B,
            'delete': 0x2E, 'backspace': 0x08, 'ctrl': 0x11, 'alt': 0x12,
            'shift': 0x10, 'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
            'Key.enter': 0x0D, 'Key.tab': 0x09, 'Key.space': 0x20, 'Key.esc': 0x1B,
            'Key.delete': 0x2E, 'Key.backspace': 0x08, 'Key.ctrl_l': 0x11, 'Key.ctrl_r': 0x11,
            'Key.alt_l': 0x12, 'Key.alt_r': 0x12, 'Key.shift_l': 0x10, 'Key.shift_r': 0x10,
            'Key.up': 0x26, 'Key.down': 0x28, 'Key.left': 0x25, 'Key.right': 0x27
        }
        
        key_str_lower = key_str.lower()
        if key_str_lower in key_map:
            return key_map[key_str_lower]
        
        # Handle regular characters (a-z, 0-9)
        if len(key_str) == 1:
            char_upper = key_str.upper()
            # Letters (VK codes are sequential)
            if 'A' <= char_upper <= 'Z':
                return ord(char_upper)
            # Numbers
            if '0' <= char_upper <= '9':
                return ord(char_upper)
        
        # Fallback: use ord()
        try:
            return ord(key_str.upper())
        except:
            return None
    
    def parse_key(self, key_str: str):
        """Parse key string to Key object"""
        if key_str.startswith("Key."):
            try:
                return getattr(Key, key_str.split(".", 1)[1])
            except AttributeError:
                print(f"[Parse] Unknown special key: {key_str}")
                return None
        return key_str
