import ctypes
from ctypes import wintypes
import sys

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_MOUSE_LL = 14

LowLevelMouseProc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

def low_level_mouse_proc(nCode, wParam, lParam):
    return user32.CallNextHookEx(None, nCode, wParam, lParam)

def main():
    mouse_proc_ptr = LowLevelMouseProc(low_level_mouse_proc)
    hook_id = user32.SetWindowsHookExW(WH_MOUSE_LL, mouse_proc_ptr, kernel32.GetModuleHandleW(None), 0)
    if not hook_id:
        err = kernel32.GetLastError()
        print(f"Failed to install hook. GetLastError: {err}")
        sys.exit(1)
    else:
        print("Hook installed successfully. Ctrl+C to exit.")
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

if __name__ == "__main__":
    main()
