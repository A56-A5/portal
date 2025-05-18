import ctypes
import os
import atexit

SPI_SETCURSORS = 0x0057
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

# Paths to Windows default Aero cursors
system_cursor_dir = r"C:\Windows\Cursors"
default_cursors = {
    'arrow': os.path.join(system_cursor_dir, 'aero_arrow.cur'),
    'iBeam': os.path.join(system_cursor_dir, 'aero_ibeam.cur'),
    'hand': os.path.join(system_cursor_dir, 'aero_link.cur'),
}

# Path to your invisible cursor file
invisible_cursor_path = os.path.join(os.getcwd(), 'invisible.cur')

# Cursor types in the registry
cursor_registry_keys = {
    'arrow': 'Arrow',
    'ibeam': 'IBeam',
    'hand': 'Hand',
}

import winreg

def set_cursor_scheme(cursor_map):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                        r"Control Panel\Cursors", 0, winreg.KEY_SET_VALUE) as key:
        for name, path in cursor_map.items():
            if name in cursor_registry_keys:
                winreg.SetValueEx(key, cursor_registry_keys[name], 0, winreg.REG_SZ, path)
    ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None,
                                                SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)

def hide_cursor():
    invisible_map = {k: invisible_cursor_path for k in default_cursors}
    set_cursor_scheme(invisible_map)

def restore_cursor():
    set_cursor_scheme(default_cursors)

# Register to restore cursor on exit
atexit.register(restore_cursor)

# Run your app logic here
if __name__ == "__main__":
    hide_cursor()
    input("App is running with invisible cursor. Press Enter to exit...")