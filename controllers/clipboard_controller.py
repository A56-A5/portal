"""
Clipboard Controller - Handles clipboard operations across different operating systems
Supports text, images, and other formats using base64 encoding
Saves received images/files to a dedicated clipboard folder
"""
import threading
import platform
import subprocess
import base64
import os
import io
from datetime import datetime
from typing import Optional, Tuple

class ClipboardController:
    def __init__(self, save_to_folder=True):
        self.lock = threading.Lock()
        self.os_type = platform.system().lower()
        self.save_to_folder = save_to_folder
        self.clipboard_folder = "clipboard"
        self._init_clipboard_functions()
        self._ensure_clipboard_folder()
    
    def _ensure_clipboard_folder(self):
        """Create clipboard folder if it doesn't exist"""
        if self.save_to_folder:
            try:
                if not os.path.exists(self.clipboard_folder):
                    os.makedirs(self.clipboard_folder)
                    print(f"[Clipboard] Created folder: {self.clipboard_folder}")
            except Exception as e:
                print(f"[Clipboard] Error creating folder: {e}")
    
    def _save_to_folder(self, data: bytes, format_type: str):
        """Save received clipboard data to the clipboard folder"""
        try:
            # Clear old temp files first
            if format_type == "image":
                # Remove all old temp images
                for filename in os.listdir(self.clipboard_folder):
                    if filename.startswith("temp_image") and filename.endswith((".png", ".jpg", ".jpeg", ".bmp")):
                        try:
                            os.remove(os.path.join(self.clipboard_folder, filename))
                        except:
                            pass
                
                filename = "temp_image.png"
                filepath = os.path.join(self.clipboard_folder, filename)
                with open(filepath, 'wb') as f:
                    f.write(data)
                print(f"[Clipboard] Temp image saved: {filepath}")
            else:
                filename = "temp_text.txt"
                filepath = os.path.join(self.clipboard_folder, filename)
                with open(filepath, 'wb') as f:
                    f.write(data)
                print(f"[Clipboard] Temp text saved: {filepath}")
        except Exception as e:
            print(f"[Clipboard] Error saving to folder: {e}")
    
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
                            
                            # Convert DIB to PNG format for cross-platform compatibility
                            try:
                                from PIL import Image
                                
                                # DIB format: First 40 bytes are BITMAPINFOHEADER
                                # We need to reconstruct the bitmap to load it
                                if len(data) < 40:
                                    raise Exception("DIB data too short")
                                
                                # Read BITMAPINFOHEADER to get dimensions and bit depth
                                width = int.from_bytes(data[0:4], 'little', signed=True)
                                height = int.from_bytes(data[4:8], 'little', signed=True)
                                bits_per_pixel = int.from_bytes(data[14:16], 'little')
                                
                                # Convert DIB to image by creating a temporary BMP file
                                # DIB is essentially a BMP without the 14-byte header
                                bmp_header = b'BM'  # BMP signature
                                file_size = (len(data) + 54).to_bytes(4, 'little')
                                reserved = b'\x00\x00\x00\x00'
                                data_offset = b'\x36\x00\x00\x00'  # 54 in little-endian
                                dib_header_size = b'\x28\x00\x00\x00'  # 40 in little-endian
                                
                                # Skip the existing BITMAPINFOHEADER and rebuild with proper header
                                info_header = data[0:40]
                                pixel_data = data[40:]
                                
                                # Reconstruct BMP file
                                bmp_file = bmp_header + file_size + reserved + data_offset
                                bmp_file += info_header + pixel_data
                                
                                # Load and convert to PNG
                                img = Image.open(io.BytesIO(bmp_file))
                                output = io.BytesIO()
                                img.save(output, format='PNG')
                                png_data = output.getvalue()
                                
                                encoded = base64.b64encode(png_data).decode('utf-8')
                                return f"image:{encoded}"
                                
                            except (ImportError, Exception) as e:
                                # If conversion fails, just encode the raw DIB data
                                print(f"[Clipboard] DIB to PNG conversion failed: {e}, using raw DIB")
                                encoded = base64.b64encode(data).decode('utf-8')
                                return f"image:{encoded}"
                        except Exception as e:
                            print(f"[Clipboard] Error getting image: {e}")
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
                            # Try to use PIL to convert image to proper format
                            try:
                                from PIL import Image
                                
                                # Try to open as image and convert
                                img = Image.open(io.BytesIO(decoded_data))
                                
                                # Convert to RGB if needed
                                if img.mode not in ('RGB', 'RGBA'):
                                    img = img.convert('RGB')
                                
                                # Save as BMP to get proper DIB format
                                output = io.BytesIO()
                                img.save(output, format='BMP')
                                bmp_data = output.getvalue()
                                
                                # Extract DIB from BMP (skip BMP file header, 14 bytes)
                                if len(bmp_data) > 14:
                                    dib_data = bmp_data[14:]  # Remove BMP header
                                    self.win32clipboard.SetClipboardData(self.win32con.CF_DIB, dib_data)
                                    
                                    # Save PNG version to temp folder
                                    if self.save_to_folder:
                                        self._save_to_folder(decoded_data, format_type)
                                else:
                                    # Invalid data, try as raw
                                    self.win32clipboard.SetClipboardData(self.win32con.CF_DIB, decoded_data)
                            except (ImportError, Exception) as e:
                                print(f"[Clipboard] Image conversion failed: {e}")
                                # Fallback: try to set raw data as DIB
                                # If it's already in DIB format, this should work
                                self.win32clipboard.SetClipboardData(self.win32con.CF_DIB, decoded_data)
                                
                                # Try to save anyway
                                if self.save_to_folder:
                                    self._save_to_folder(decoded_data, format_type)
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

