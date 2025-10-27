"""
Clipboard Controller - Handles clipboard operations across different operating systems
"""
import threading
import platform
import subprocess
from typing import Optional

class ClipboardController:
    def __init__(self):
        self.lock = threading.Lock()
        self.os_type = platform.system().lower()
        self._init_clipboard_functions()
    
    def _init_clipboard_functions(self):
        """Initialize OS-specific clipboard functions"""
        if self.os_type == "windows":
            try:
                import win32clipboard
                self.win32clipboard = win32clipboard
            except ImportError:
                import pyperclip as pypc
                self._fallback = pypc
                self.win32clipboard = None
        elif self.os_type == "linux":
            self.win32clipboard = None
        else:
            import pyperclip as pypc
            self._fallback = pypc
            self.win32clipboard = None
    
    def get_clipboard(self) -> str:
        """Get clipboard content"""
        with self.lock:
            if self.os_type == "windows" and self.win32clipboard:
                try:
                    self.win32clipboard.OpenClipboard()
                    data = self.win32clipboard.GetClipboardData()
                    self.win32clipboard.CloseClipboard()
                    return data
                except Exception:
                    try:
                        self.win32clipboard.CloseClipboard()
                    except:
                        pass
                    return ""
            
            elif self.os_type == "linux":
                try:
                    return subprocess.check_output(['xclip', '-selection', 'clipboard', '-o']).decode()
                except Exception:
                    return ""
            
            else:
                # Fallback for other OS or when win32clipboard is not available
                import pyperclip
                return pyperclip.paste()
    
    def set_clipboard(self, text: str) -> bool:
        """Set clipboard content"""
        with self.lock:
            if self.os_type == "windows" and self.win32clipboard:
                try:
                    self.win32clipboard.OpenClipboard()
                    self.win32clipboard.EmptyClipboard()
                    self.win32clipboard.SetClipboardText(text)
                    self.win32clipboard.CloseClipboard()
                    return True
                except Exception:
                    try:
                        self.win32clipboard.CloseClipboard()
                    except:
                        pass
                    return False
            
            elif self.os_type == "linux":
                try:
                    p = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
                    p.communicate(input=text.encode())
                    return True
                except Exception:
                    return False
            
            else:
                # Fallback for other OS
                import pyperclip
                try:
                    pyperclip.copy(text)
                    return True
                except:
                    return False

