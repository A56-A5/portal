"""
Keyboard Controller - Handles keyboard input control
Uses win32api on Windows for better compatibility in secure contexts (lockscreen, password fields)
"""
import platform
import time
from pynput.keyboard import Controller as PynputKeyboardController, Key

class KeyboardController:
    def __init__(self):
        self._controller = PynputKeyboardController()
        self.os_type = platform.system().lower()
        
        # Initialize attributes first
        self.win32api = None
        self.win32con = None
        self.use_win32 = False
        self.subprocess = None
        self.use_xdotool = False
        
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
        elif self.os_type == "linux":
            # Use xdotool for Linux (better for secure contexts like lockscreen)
            try:
                import subprocess
                self.subprocess = subprocess
                # Check if xdotool is available
                result = subprocess.run(['which', 'xdotool'], capture_output=True)
                self.use_xdotool = result.returncode == 0
                if self.use_xdotool:
                    print("[Keyboard] Using xdotool for Linux keyboard input")
                else:
                    print("[Keyboard] Warning: xdotool not found. Install with: sudo apt install xdotool")
            except:
                self.use_xdotool = False
    
    def press(self, key):
        """Press a key"""
        if self.use_win32 and isinstance(key, str) and len(key) == 1:
            # Use win32 for single character keys (better for secure contexts)
            self._win32_press(key)
        elif self.use_xdotool and isinstance(key, str) and len(key) == 1:
            # Use xdotool for single character keys on Linux
            self._xdotool_press(key)
        else:
            # For Key objects or multi-character strings, use pynput
            self._controller.press(key)
    
    def release(self, key):
        """Release a key"""
        if self.use_win32 and isinstance(key, str) and len(key) == 1:
            self._win32_release(key)
        elif self.use_xdotool and isinstance(key, str) and len(key) == 1:
            # xdotool handles press+release in one command
            pass  # No action needed for release with xdotool
        else:
            # For Key objects or multi-character strings, use pynput
            self._controller.release(key)
    
    def tap(self, key):
        """Tap a key (press and release) - useful for characters"""
        if self.use_win32 and isinstance(key, str) and len(key) == 1:
            # Use win32 for single character keys with proper shift handling
            self._win32_tap(key)
        elif self.use_xdotool and isinstance(key, str) and len(key) == 1:
            # Use xdotool for single character keys
            self._xdotool_press(key)
        else:
            # For Key objects or multi-character strings, use pynput
            self._controller.press(key)
            self._controller.release(key)
    
    def _win32_tap(self, key_str):
        """Tap key using win32api with proper shift handling"""
        try:
            # Get VK code and shift state
            vk_and_shift = self.win32api.VkKeyScan(ord(key_str))
            vk = vk_and_shift & 0xFF  # Lower 8 bits are the VK code
            shift_state = (vk_and_shift >> 8) & 0xFF  # High byte has shift state
            
            # Press shift if needed
            if shift_state & 0x01:  # Shift key needed
                self.win32api.keybd_event(0x10, 0, 0, 0)  # Press shift
            
            # Press the actual key
            self.win32api.keybd_event(vk, 0, 0, 0)
            
            # Brief delay for key press
            time.sleep(0.01)
            
            # Release the key
            self.win32api.keybd_event(vk, 0, self.win32con.KEYEVENTF_KEYUP, 0)
            
            # Release shift if it was pressed
            if shift_state & 0x01:
                self.win32api.keybd_event(0x10, 0, self.win32con.KEYEVENTF_KEYUP, 0)
        except Exception as e:
            print(f"[Keyboard] Win32 tap error: {e}, falling back to pynput")
            try:
                self._controller.tap(key_str)
            except:
                pass
    
    def _win32_press(self, key_str):
        """Press key using win32api for better system-level support"""
        try:
            vk = self._key_to_vk(key_str)
            if vk:
                # For special characters, we might need to handle shift key
                # VkKeyScan returns high-order byte for shift state
                vk_and_shift = self.win32api.VkKeyScan(ord(key_str))
                shift_state = (vk_and_shift >> 8) & 0xFF
                
                # If shift is needed, press it
                if shift_state & 0x01:  # Shift key needed
                    self.win32api.keybd_event(0x10, 0, 0, 0)  # Press shift
                
                # Press the actual key
                self.win32api.keybd_event(vk, 0, 0, 0)
            else:
                # Fallback to direct typing if VK lookup fails
                # Use keybd_event with the raw key
                self._controller.tap(key_str)
        except Exception as e:
            print(f"[Keyboard] Win32 press error: {e}, falling back to pynput")
            try:
                self._controller.tap(key_str)
            except:
                pass
    
    def _win32_release(self, key_str):
        """Release key using win32api"""
        try:
            vk = self._key_to_vk(key_str)
            if vk:
                # Release the key
                self.win32api.keybd_event(vk, 0, self.win32con.KEYEVENTF_KEYUP, 0)
                
                # Release shift if it was pressed
                vk_and_shift = self.win32api.VkKeyScan(ord(key_str))
                shift_state = (vk_and_shift >> 8) & 0xFF
                if shift_state & 0x01:
                    self.win32api.keybd_event(0x10, 0, self.win32con.KEYEVENTF_KEYUP, 0)
        except Exception as e:
            print(f"[Keyboard] Win32 release error: {e}")
    
    def _xdotool_press(self, key_str):
        """Press key using xdotool for better Linux support"""
        try:
            key = self._key_to_xdotool(key_str)
            if key:
                # xdotool types the key (press+release)
                self.subprocess.run(['xdotool', 'key', key], capture_output=True)
        except Exception as e:
            print(f"[Keyboard] xdotool press error: {e}")
    
    def _key_to_xdotool(self, key_str):
        """Convert key string to xdotool key name"""
        # Handle special keys for xdotool
        key_map = {
            'enter': 'Return', 'tab': 'Tab', 'space': 'space', 'esc': 'Escape',
            'delete': 'Delete', 'backspace': 'BackSpace', 'ctrl': 'ctrl',
            'alt': 'alt', 'shift': 'Shift', 'up': 'Up', 'down': 'Down',
            'left': 'Left', 'right': 'Right',
            'Key.enter': 'Return', 'Key.tab': 'Tab', 'Key.space': 'space',
            'Key.esc': 'Escape', 'Key.delete': 'Delete', 'Key.backspace': 'BackSpace',
            'Key.ctrl_l': 'ctrl', 'Key.ctrl_r': 'ctrl_r', 'Key.alt_l': 'alt',
            'Key.alt_r': 'alt_r', 'Key.shift_l': 'Shift', 'Key.shift_r': 'Shift_R',
            'Key.up': 'Up', 'Key.down': 'Down', 'Key.left': 'Left', 'Key.right': 'Right',
            'Key.caps_lock': 'Caps_Lock', 'Key.num_lock': 'Num_Lock',
            'Key.f1': 'F1', 'Key.f2': 'F2', 'Key.f3': 'F3', 'Key.f4': 'F4',
            'Key.f5': 'F5', 'Key.f6': 'F6', 'Key.f7': 'F7', 'Key.f8': 'F8',
            'Key.f9': 'F9', 'Key.f10': 'F10', 'Key.f11': 'F11', 'Key.f12': 'F12'
        }
        
        key_str_lower = key_str.lower()
        if key_str_lower in key_map:
            return key_map[key_str_lower]
        
        # Handle regular characters - xdotool accepts them directly
        if len(key_str) == 1:
            return key_str
        
        # Fallback
        return key_str
    
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
        
        # Handle regular characters
        if len(key_str) == 1:
            # For special characters, use VkKeyScan which gets the VK for any character
            # including punctuation, numbers with shift, etc.
            try:
                vk_and_shift = self.win32api.VkKeyScan(ord(key_str))
                return vk_and_shift & 0xFF  # Lower 8 bits are the VK code
            except:
                # Fallback to direct lookup
                char_upper = key_str.upper()
                # Letters
                if 'A' <= char_upper <= 'Z':
                    return ord(char_upper)
                # Numbers
                if '0' <= char_upper <= '9':
                    return ord(char_upper)
        
        # Fallback
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
