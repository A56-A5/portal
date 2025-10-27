"""
Clipboard Controller - Handles clipboard operations across different operating systems
Supports text, images, and other formats using base64 encoding
"""
import threading
import platform
import subprocess
import base64
from typing import Optional, Tuple

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
                import win32con
                self.win32clipboard = win32clipboard
                self.win32con = win32con
            except ImportError:
                import pyperclip as pypc
                self._fallback = pypc
                self.win32clipboard = None
                self.win32con = None
        elif self.os_type == "linux":
            self.win32clipboard = None
            self.win32con = None
        else:
            import pyperclip as pypc
            self._fallback = pypc
            self.win32clipboard = None
            self.win32con = None
    
    def get_clipboard(self) -> str:
        """Get clipboard content as base64 encoded string (supports images and binary data)"""
        with self.lock:
            if self.os_type == "windows" and self.win32clipboard:
                try:
                    self.win32clipboard.OpenClipboard()
                    
                    # Try to get image (bitmap) first
                    if self.win32clipboard.IsClipboardFormatAvailable(self.win32con.CF_DIB):
                        try:
                            data = self.win32clipboard.GetClipboardData(self.win32con.CF_DIB)
                            self.win32clipboard.CloseClipboard()
                            # Convert to base64
                            encoded = base64.b64encode(data).decode('utf-8')
                            return f"image:{encoded}"
                        except Exception:
                            pass
                    
                    # Try text
                    if self.win32clipboard.IsClipboardFormatAvailable(self.win32con.CF_UNICODETEXT):
                        try:
                            data = self.win32clipboard.GetClipboardData(self.win32con.CF_UNICODETEXT)
                            self.win32clipboard.CloseClipboard()
                            # Encode text to base64 to handle special characters
                            encoded = base64.b64encode(data.encode('utf-8')).decode('utf-8')
                            return f"text:{encoded}"
                        except Exception:
                            pass
                    
                    # Fallback to plain text
                    try:
                        data = self.win32clipboard.GetClipboardData()
                        self.win32clipboard.CloseClipboard()
                        encoded = base64.b64encode(str(data).encode('utf-8')).decode('utf-8')
                        return f"text:{encoded}"
                    except Exception:
                        pass
                    
                    self.win32clipboard.CloseClipboard()
                    return ""
                except Exception:
                    try:
                        self.win32clipboard.CloseClipboard()
                    except:
                        pass
                    return ""
            
            elif self.os_type == "linux":
                try:
                    # Try to get text first
                    try:
                        text_data = subprocess.check_output(['xclip', '-selection', 'clipboard', '-o'], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
                        encoded = base64.b64encode(text_data.encode('utf-8')).decode('utf-8')
                        return f"text:{encoded}"
                    except:
                        pass
                    
                    # Try image (PNG)
                    try:
                        image_data = subprocess.check_output(['xclip', '-selection', 'clipboard', '-t', 'image/png', '-o'], stderr=subprocess.DEVNULL)
                        encoded = base64.b64encode(image_data).decode('utf-8')
                        return f"image:{encoded}"
                    except:
                        pass
                    
                    return ""
                except Exception:
                    return ""
            
            else:
                # Fallback for other OS
                import pyperclip
                try:
                    data = pyperclip.paste()
                    encoded = base64.b64encode(data.encode('utf-8')).decode('utf-8')
                    return f"text:{encoded}"
                except:
                    return ""
    
    def set_clipboard(self, encoded_data: str) -> bool:
        """Set clipboard content (decodes base64 and sets appropriate format)"""
        with self.lock:
            try:
                # Parse format prefix (image: or text:)
                if ":" not in encoded_data:
                    # Old format without prefix, treat as text
                    format_type = "text"
                    base64_data = encoded_data
                else:
                    format_type, base64_data = encoded_data.split(":", 1)
                
                # Decode base64
                decoded_data = base64.b64decode(base64_data)
                
                if self.os_type == "windows" and self.win32clipboard:
                    try:
                        self.win32clipboard.OpenClipboard()
                        self.win32clipboard.EmptyClipboard()
                        
                        if format_type == "image":
                            # Set as DIB (Device Independent Bitmap)
                            self.win32clipboard.SetClipboardData(self.win32con.CF_DIB, decoded_data)
                        else:
                            # Set as text
                            text_data = decoded_data.decode('utf-8')
                            self.win32clipboard.SetClipboardText(text_data)
                        
                        self.win32clipboard.CloseClipboard()
                        return True
                    except Exception as e:
                        try:
                            self.win32clipboard.CloseClipboard()
                        except:
                            pass
                        print(f"[Clipboard] Error setting data: {e}")
                        return False
                
                elif self.os_type == "linux":
                    try:
                        if format_type == "image":
                            # Set as PNG image
                            p = subprocess.Popen(
                                ['xclip', '-selection', 'clipboard', '-t', 'image/png'],
                                stdin=subprocess.PIPE
                            )
                            p.communicate(input=decoded_data)
                        else:
                            # Set as text
                            text_data = decoded_data.decode('utf-8')
                            p = subprocess.Popen(
                                ['xclip', '-selection', 'clipboard'],
                                stdin=subprocess.PIPE
                            )
                            p.communicate(input=text_data.encode('utf-8'))
                        return True
                    except Exception as e:
                        print(f"[Clipboard] Error setting data: {e}")
                        return False
                
                else:
                    # Fallback for other OS
                    import pyperclip
                    try:
                        text_data = decoded_data.decode('utf-8')
                        pyperclip.copy(text_data)
                        return True
                    except Exception as e:
                        print(f"[Clipboard] Error setting data: {e}")
                        return False
                        
            except Exception as e:
                print(f"[Clipboard] Error parsing clipboard data: {e}")
                return False

