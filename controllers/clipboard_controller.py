"""
Clipboard Controller - Handles clipboard operations across different operating systems
Supports text, images, and other formats using base64 encoding
"""
import base64
import io
import os
import platform
import subprocess
import threading
import urllib.parse
from typing import Optional, Tuple

class ClipboardController:
    def __init__(self, save_to_folder=False):
        self.lock = threading.Lock()
        self.os_type = platform.system().lower()
        self.save_to_folder = save_to_folder
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
            try:
                # Strictly require WAYLAND_DISPLAY and a successful wl-paste check
                if os.environ.get('WAYLAND_DISPLAY'):
                    res = subprocess.run(['wl-paste', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if res.returncode == 0:
                        self.linux_tool = 'wl-clipboard'
                    else:
                        raise Exception("wl-clipboard missing or fails")
                else:
                    raise Exception("Not in Wayland")
            except:
                try:
                    subprocess.run(['xclip', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    self.linux_tool = 'xclip'
                except:
                    self.linux_tool = 'fallback'
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
                except Exception as e:
                    print(f"[Clipboard] Failed to open: {e}")
                    return ""
                    
                try:
                    # Try to get files (CF_HDROP) first
                    if self.win32clipboard.IsClipboardFormatAvailable(self.win32con.CF_HDROP):
                        try:
                            files = self.win32clipboard.GetClipboardData(self.win32con.CF_HDROP)
                            if files:
                                print(f"[Clipboard] Detected {len(files)} files")
                                encoded = base64.b64encode("\n".join(files).encode('utf-8')).decode('utf-8')
                                return f"files:{encoded}"
                        except Exception as e:
                            print(f"[Clipboard] Error reading files: {e}")
                    
                    # Try to get image (bitmap)
                    if self.win32clipboard.IsClipboardFormatAvailable(self.win32con.CF_DIB):
                        try:
                            data = self.win32clipboard.GetClipboardData(self.win32con.CF_DIB)
                            print("[Clipboard] Detected image (DIB)")
                            try:
                                from PIL import Image
                                if len(data) >= 40:
                                    bmp_header = b'BM'
                                    file_size = (len(data) + 54).to_bytes(4, 'little')
                                    data_offset = b'\x36\x00\x00\x00'
                                    bmp_file = bmp_header + file_size + b'\x00\x00\x00\x00' + data_offset + data
                                    img = Image.open(io.BytesIO(bmp_file))
                                    output = io.BytesIO()
                                    img.save(output, format='PNG')
                                    encoded = base64.b64encode(output.getvalue()).decode('utf-8')
                                    return f"image:{encoded}"
                            except Exception:
                                encoded = base64.b64encode(data).decode('utf-8')
                                return f"image:{encoded}"
                        except Exception as e:
                            print(f"[Clipboard] Error getting image data: {e}")

                    # Try text
                    if self.win32clipboard.IsClipboardFormatAvailable(self.win32con.CF_UNICODETEXT):
                        try:
                            data = self.win32clipboard.GetClipboardData(self.win32con.CF_UNICODETEXT)
                            if data:
                                # Data is already unicode from win32clipboard for CF_UNICODETEXT
                                encoded = base64.b64encode(data.encode('utf-8')).decode('utf-8')
                                return f"text:{encoded}"
                        except Exception:
                            pass
                    return ""
                finally:
                    try:
                        self.win32clipboard.CloseClipboard()
                    except:
                        pass
            
            elif self.os_type == "linux":
                import urllib.parse
                if self.linux_tool == 'wl-clipboard':
                    # Try files
                    try:
                        uris = subprocess.check_output(['wl-paste', '-t', 'text/uri-list'], stderr=subprocess.DEVNULL).decode('utf-8').strip()
                        files = [urllib.parse.unquote(u.replace('file://', '')) for u in uris.splitlines() if u.startswith('file://')]
                        if files:
                            encoded = base64.b64encode("\n".join(files).encode('utf-8')).decode('utf-8')
                            return f"files:{encoded}"
                    except: pass
                    # Try image
                    try:
                        img_data = subprocess.check_output(['wl-paste', '-t', 'image/png'], stderr=subprocess.DEVNULL)
                        return f"image:{base64.b64encode(img_data).decode('utf-8')}"
                    except: pass
                    # Text
                    try:
                        text = subprocess.check_output(['wl-paste'], stderr=subprocess.DEVNULL).decode('utf-8')
                        return f"text:{base64.b64encode(text.encode('utf-8')).decode('utf-8')}"
                    except: pass
                else:
                    # xclip
                    try:
                        try:
                            uris = subprocess.check_output(['xclip', '-selection', 'clipboard', '-t', 'text/uri-list', '-o'], stderr=subprocess.DEVNULL).decode('utf-8').strip()
                            files = [urllib.parse.unquote(u.replace('file://', '')) for u in uris.splitlines() if u.startswith('file://')]
                            if files:
                                return f"files:{base64.b64encode(chr(10).join(files).encode('utf-8')).decode('utf-8')}"
                        except: pass
                        try:
                            text = subprocess.check_output(['xclip', '-selection', 'clipboard', '-o'], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
                            return f"text:{base64.b64encode(text.encode('utf-8')).decode('utf-8')}"
                        except: pass
                    except: pass
                return ""
            else:
                import pyperclip
                try:
                    data = pyperclip.paste()
                    return f"text:{base64.b64encode(data.encode('utf-8')).decode('utf-8')}"
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
                print(f"[Clipboard] Setting clipboard format: {format_type}")
                
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
                                else:
                                    # Invalid data, try as raw
                                    self.win32clipboard.SetClipboardData(self.win32con.CF_DIB, decoded_data)
                            except (ImportError, Exception) as e:
                                print(f"[Clipboard] Image conversion failed: {e}")
                                # Fallback: try to set raw data as DIB
                                self.win32clipboard.SetClipboardData(self.win32con.CF_DIB, decoded_data)
                        elif format_type == "files":
                            try:
                                files = decoded_data.decode('utf-8').splitlines()
                                import struct
                                # DROPFILES header: pFiles(4), pt.x(4), pt.y(4), fNC(4), fWide(4) = 20 bytes
                                # struct.pack("IIIII", 20, 0, 0, 0, 1)
                                header = struct.pack("LLLLL", 20, 0, 0, 0, 1)
                                # Unicode paths separated by \0, terminated by \0\0
                                # In UTF-16-LE, each \0 is 2 bytes. We need a double wide-char null terminator.
                                files_unicode = ("\0".join(files) + "\0\0").encode("utf-16-le")
                                dropfiles_data = header + files_unicode
                                self.win32clipboard.SetClipboardData(self.win32con.CF_HDROP, dropfiles_data)
                            except Exception as e:
                                print(f"[Clipboard] File sync failed: {e}")
                                # Fallback to text
                                self.win32clipboard.SetClipboardText(decoded_data.decode('utf-8'))
                        else:
                            # Set as unicode text to avoid MBCS codec issues
                            text_data = decoded_data.decode('utf-8')
                            self.win32clipboard.SetClipboardData(self.win32con.CF_UNICODETEXT, text_data)
                        
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
                            tool = 'wl-copy' if self.linux_tool == 'wl-clipboard' else 'xclip'
                            cmd = [tool, '-t', 'image/png'] if tool == 'wl-copy' else ['xclip', '-selection', 'clipboard', '-t', 'image/png']
                            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
                            p.communicate(input=decoded_data)
                        elif format_type == "files":
                            # Setting files on Linux is harder, we provide the paths as text/uri-list
                            import urllib.parse
                            files = decoded_data.decode('utf-8').splitlines()
                            
                            uri_list = []
                            for f in files:
                                f = os.path.abspath(f)
                                # Proper URI escaping for Linux (important for spaces)
                                url_path = urllib.parse.quote(f)
                                if not url_path.startswith('/'):
                                    url_path = '/' + url_path
                                uri_list.append(f"file://{url_path}")
                            
                            # Standard URI list (CRLF separated)
                            uris = "\r\n".join(uri_list) + "\r\n"
                            
                            # GNOME (Nautilus) specifically often wants x-special/gnome-copied-files
                            gnome_paths = "copy\n" + "\n".join(uri_list)
                            
                            tool = 'wl-copy' if self.linux_tool == 'wl-clipboard' else 'xclip'
                            
                            def run_copy(mtype, data):
                                if tool == 'wl-copy':
                                    cmd = ['wl-copy', '-t', mtype]
                                else:
                                    cmd = ['xclip', '-selection', 'clipboard', '-t', mtype]
                                try:
                                    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
                                    p.communicate(input=data.encode('utf-8'))
                                except: pass

                            run_copy('text/uri-list', uris)
                            run_copy('x-special/gnome-copied-files', gnome_paths)
                        else:
                            # Set as text
                            text_data = decoded_data.decode('utf-8')
                            tool = 'wl-copy' if self.linux_tool == 'wl-clipboard' else 'xclip'
                            cmd = [tool] if tool == 'wl-copy' else ['xclip', '-selection', 'clipboard']
                            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
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

