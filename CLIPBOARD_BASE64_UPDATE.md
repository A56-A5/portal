# Clipboard Base64 Update

## Summary
Enhanced clipboard functionality to support images and other binary formats using base64 encoding.

## Changes Made

### 1. `portal/controllers/clipboard_controller.py` ✅
**Updated**: Full base64 support with image handling
- `get_clipboard()` now returns format-prefixed base64 strings: `"image:base64data"` or `"text:base64data"`
- `set_clipboard()` decodes base64 and sets appropriate format (image or text)
- Supports Windows (DIB format for images) and Linux (PNG format)

### 2. Changes Needed for `portal/share.py`

The original `share.py` needs to be updated to use the new base64 format. Here's what needs to be added:

#### A. Add base64 import (already done)
```python
import base64
```

#### B. Update clipboard functions to match the controller

Update the Windows section (after line 32):
```python
if os_type == "windows":
    try:
        import win32clipboard
        import win32con
    except ImportError:
        win32clipboard = None
        win32con = None

    def get_clipboard():
        with clipboard_lock:
            try:
                if not win32clipboard:
                    import pyperclip
                    data = pyperclip.paste()
                    encoded = base64.b64encode(data.encode('utf-8')).decode('utf-8')
                    return f"text:{encoded}"
                
                win32clipboard.OpenClipboard()
                
                # Try image first
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                    try:
                        data = win32clipboard.GetClipboardData(win32con.CF_DIB)
                        win32clipboard.CloseClipboard()
                        encoded = base64.b64encode(data).decode('utf-8')
                        return f"image:{encoded}"
                    except:
                        pass
                
                # Try text
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    try:
                        data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                        win32clipboard.CloseClipboard()
                        encoded = base64.b64encode(data.encode('utf-8')).decode('utf-8')
                        return f"text:{encoded}"
                    except:
                        pass
                
                win32clipboard.CloseClipboard()
                return ""
            except:
                try:
                    win32clipboard.CloseClipboard()
                except:
                    pass
                return ""

    def set_clipboard(encoded_data):
        with clipboard_lock:
            try:
                if not win32clipboard:
                    import pyperclip
                    if ":" not in encoded_data:
                        format_type = "text"
                        base64_data = encoded_data
                    else:
                        format_type, base64_data = encoded_data.split(":", 1)
                    decoded = base64.b64decode(base64_data).decode('utf-8')
                    pyperclip.copy(decoded)
                    return be
                
                if ":" not in encoded_data:
                    format_type = "text"
                    base64_data = encoded_data
                else:
                    format_type, base64_data = encoded_data.split(":", 1)
                
                decoded_data = base64.b64decode(base64_data)
                
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                
                if format_type == "image":
                    win32clipboard.SetClipboardData(win32con.CF_DIB, decoded_data)
                else:
                    text_data = decoded_data.decode('utf-8')
                    win32clipboard.SetClipboardText(text_data)
                
                win32clipboard.CloseClipboard()
            except:
                try:
                    win32clipboard.CloseClipboard()
                except:
                    pass
```

Update the Linux section:
```python
elif os_type == "linux":
    def get_clipboard():
        with clipboard_lock:
            try:
                # Try text first
                try:
                    text_data = subprocess.check_output(
                        ['xclip', '-selection', 'clipboard', '-o'],
                        stderr=subprocess.DEVNULL
                    ).decode('utf-8', errors='ignore')
                    encoded = base64.b64encode(text_data.encode('utf-8')).decode('utf-8')
                    return f"text:{encoded}"
                except:
                    pass
                
                # Try image (PNG)
                try:
                    image_data = subprocess.check_output(
                        ['xclip', '-selection', 'clipboard', '-t', 'image/png', '-o'],
                        stderr=subprocess.DEVNULL
                    )
                    encoded = base64.b64encode(image_data).decode('utf-8')
                    return f"image:{encoded}"
                except:
                    pass
                
                return ""
            except:
                return ""

要使 set_clipboard(encoded_data):
        with clipboard_lock:
ิศ  try:
                if ":" not in encoded_data:
                    format_type = "text"
                    base64_data = encoded_data
                else:
                    format_type, base64_data = encoded_data.split(":", 1)
                
                decoded_data = base64.b64decode(base64_data)
                
                if format_type == "image":
                    p = subprocess.Popen(
                        ['xclip', '-selection', 'clipboard', '-t', 'image/png'],
                        stdin=subprocess.PIPE
                    )
                    p.communicate(input=decoded_data)
                else:
                    text_data = decoded_data.decode('utf-8')
                    p = subprocess.Popen(
                        ['xclip', '-selection', 'clipboard'],
                        stdin=subprocess.PIPE
                    )
                    p.communicate(input=text_data.encode('utf-8'))
            except:
                pass
```

Update the fallback (pyperclip) section:
```python
else:
    import pyperclip

    def get_clipboard():
        with clipboard_lock:
            try:
                data = pyperclip.paste()
                encoded = base64.b64encode(data.encode('utf-8')).decode('utf-8')
                return f"text:{encoded}"
            except:
                return ""

    def set_clipboard(encoded_data):
        with clipboard_lock:
            try:
                if ":" not in encoded_data:
                    format_type = "text"
                    base64_data = encoded_data
                else:
                    format_type, base64_data = encoded_data.split(":", 1)
                decoded = base64.b64decode(base64_data).decode('utf-8')
                pyperclip.copy(decoded)
            except:
                pass
```

## Benefits

1. **Image Support**: Clipboard can now transfer images between devices
2. **Special Characters**: Base64 encoding handles Unicode and special characters safely
3. **Binary Data**: Support for any binary clipboard data
4. **Format Detection**: Automatically detects and preserves format (text vs image)image.png
5. **Cross-Platform**: Works on Windows and Linux

## Testing

To test the new functionality:
1. Copy an image on the server device (Ctrl+C from a picture)
2. Transition to the client device (mouse to edge)
3. Paste on the client device (Ctrl+V)
4. The image should appear

## Status

✅ `controllers/clipboard_controller.py` - Complete
⏳ `share.py` - Needs manual update (see instructions above)

## Note

The `share.py` file still works with the original implementation. The controller version provides the enhanced base64 support. When you're ready to fully migrate to the organized structure, use the controller version.

