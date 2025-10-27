"""
Keyboard Controller - Handles keyboard input control
"""
from pynput.keyboard import Controller as PynputKeyboardController, Key

class KeyboardController:
    def __init__(self):
        self._controller = PynputKeyboardController()
    
    def press(self, key):
        """Press a key"""
        self._controller.press(key)
    
    def release(self, key):
        """Release a key"""
        self._controller.release(key)
    
    def parse_key(self, key_str: str):
        """Parse key string to Key object"""
        if key_str.startswith("Key."):
            try:
                return getattr(Key, key_str.split(".", 1)[1])
            except AttributeError:
                print(f"[Parse] Unknown special key: {key_str}")
                return None
        return key_str

