# Linux Keyboard Fix - xdotool Required

## Problem
Keyboard input doesn't work in certain Linux contexts:
- App search
- Password fields
- Linux lockscreen
- Special keys (Ctrl, Alt, Shift, Enter, etc.) don't work

## Solution
Added xdotool support for better system-level keyboard input on Linux.

## Installation Required

**For Linux clients**, you need to install xdotool:

```bash
sudo apt install xdotool    # Ubuntu/Debian
sudo yum install xdotool    # Fedora/RHEL
sudo pacman -S xdotool      # Arch Linux
```

## What Changed

### 1. `controllers/keyboard_controller.py`
- Added xdotool detection and initialization
- Added `_xdotool_press()` method for Linux keyboard input
- Added `_key_to_xdotool()` to convert key strings to xdotool format
- Automatic fallback to regular pynput if xdotool not available

### 2. How It Works
- **Windows**: Uses win32api (keybd_event) for system-level input
- **Linux**: Uses xdotool for system-level input
- **Fallback**: Uses pynput for both platforms if preferred methods unavailable

## Benefits

1. **Works in secure contexts**: Lockscreen, password fields, secure UIs
2. **Better compatibility**: xdotool uses X11's XTest extension
3. **Special keys support**: All function keys, modifiers, arrows work
4. **System-level input**: Doesn't get blocked by applications

## Testing

After installing xdotool:
1. Restart Portal on Linux client
2. Try typing in:
   - App search
   - Password field
   - Lockscreen
   - Terminal
3. Test special keys: Ctrl, Alt, Shift, Enter, Tab, etc.

## Auto-Detection

The system automatically detects xdotool on startup:
- If found: Uses xdotool for all keyboard input
- If not found: Falls back to pynput (may not work in secure contexts)
- Warning message shows if xdotool is missing

## Status

✅ Windows: Uses win32api (native)
✅ Linux: Uses xdotool (requires installation)
⚠️  Linux without xdotool: Uses pynput (limited functionality)

## Alternative (if xdotool doesn't work)

If xdotool still doesn't work for some contexts, try:
```bash
sudo apt install libxdo-dev
pip install python-xlib
```

This installs X11 libraries for direct X11 input simulation.

