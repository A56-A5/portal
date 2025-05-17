import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import json
from pynput import mouse
import time
import platform
import ctypes
import os

# Platform-specific imports and structures
if platform.system() == "Windows":
    try:
        import win32api
        import win32con
        import win32gui
        from ctypes import windll, Structure, c_long, byref, c_uint, sizeof, POINTER, c_void_p, c_ulong, c_ushort, c_int

        class RAWINPUTDEVICE(Structure):
            _fields_ = [("usUsagePage", c_ushort),
                        ("usUsage", c_ushort),
                        ("dwFlags", c_ulong),
                        ("hwndTarget", c_void_p)]

        class RAWINPUTHEADER(Structure):
            _fields_ = [("dwType", c_ulong),
                        ("dwSize", c_ulong),
                        ("hDevice", c_void_p),
                        ("wParam", c_void_p)]

        class RAWMOUSE(Structure):
            _fields_ = [("usFlags", c_ushort),
                        ("ulButtons", c_ulong),
                        ("ulRawButtons", c_ulong),
                        ("lLastX", c_long),
                        ("lLastY", c_long),
                        ("ulExtraInformation", c_ulong)]

        class RAWINPUT(Structure):
            _fields_ = [("header", RAWINPUTHEADER),
                        ("data", RAWMOUSE)]

        RIM_TYPEMOUSE = 0
        RIDEV_INPUTSINK = 0x00000100
        WM_INPUT = 0x00FF
        MOUSE_MOVE_RELATIVE = 0x00

    except ImportError:
        print("[System] win32api not available")

class MouseSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mouse Sync")
        self.root.geometry("300x200")

        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        self.is_server = tk.BooleanVar(value=False)
        self.server_ip = tk.StringVar(value="127.0.0.1")
        self.port = 50007
        self.is_running = False
        self.server_socket = None
        self.client_socket = None
        self.mouse_controller = mouse.Controller()
        self.system = platform.system()
        self.use_raw_input = False

        self.virtual_x = self.screen_width // 2
        self.virtual_y = self.screen_height // 2

        self.virtual_pointer = tk.Toplevel(self.root)
        self.virtual_pointer.overrideredirect(True)
        self.virtual_pointer.attributes('-topmost', True)
        self.virtual_pointer.attributes('-alpha', 0.8)

        self.pointer_canvas = tk.Canvas(self.virtual_pointer, width=10, height=10, bg='white', highlightthickness=0)
        self.pointer_canvas.pack()
        self.pointer_canvas.create_oval(0, 0, 10, 10, fill='red', outline='red')
        self.virtual_pointer.withdraw()

        if self.system == "Windows":
            self.setup_windows_raw_input()
        self.setup_gui()

    def setup_windows_raw_input(self):
        try:
            rid = RAWINPUTDEVICE()
            rid.usUsagePage = 0x01
            rid.usUsage = 0x02
            rid.dwFlags = RIDEV_INPUTSINK
            rid.hwndTarget = self.root.winfo_id()
            if not windll.user32.RegisterRawInputDevices(byref(rid), 1, sizeof(rid)):
                print("[Windows] Failed to register raw input device")
            else:
                self.use_raw_input = True

            self.root.bind('<Map>', lambda e: self.root.focus_force())
            self.root.bind('<FocusIn>', lambda e: self.root.focus_force())
            self.root.bind(WM_INPUT, self.handle_windows_raw_input)
        except Exception as e:
            print(f"[Windows] Raw input setup error: {e}")

    def handle_windows_raw_input(self, event):
        try:
            dwSize = c_uint()
            windll.user32.GetRawInputData(event.lParam, 0x10000003, None, byref(dwSize), sizeof(RAWINPUTHEADER))
            raw = RAWINPUT()
            windll.user32.GetRawInputData(event.lParam, 0x10000003, byref(raw), byref(dwSize), sizeof(RAWINPUTHEADER))

            if raw.data.usFlags == MOUSE_MOVE_RELATIVE:
                dx = raw.data.lLastX
                dy = raw.data.lLastY

                self.virtual_x += dx
                self.virtual_y += dy
                self.virtual_x = max(0, min(self.screen_width - 1, self.virtual_x))
                self.virtual_y = max(0, min(self.screen_height - 1, self.virtual_y))

                self.virtual_pointer.geometry(f"+{self.virtual_x-5}+{self.virtual_y-5}")
                self.virtual_pointer.deiconify()

                if self.is_running and self.server_socket:
                    data = json.dumps({"type": "move", "x": self.virtual_x, "y": self.virtual_y}) + '\n'
                    self.server_socket.sendall(data.encode())
        except Exception as e:
            print(f"[Windows] Raw input error: {e}")

    def setup_gui(self):
        ttk.LabelFrame(self.root, text="Mode").pack(fill="x", padx=10, pady=5)
        ttk.Radiobutton(self.root, text="Server", variable=self.is_server, value=True).pack(anchor="w", padx=20)
        ttk.Radiobutton(self.root, text="Client", variable=self.is_server, value=False).pack(anchor="w", padx=20)
        ttk.Label(self.root, text="Server IP:").pack(pady=5)
        ttk.Entry(self.root, textvariable=self.server_ip).pack(fill="x", padx=20)
        self.start_button = ttk.Button(self.root, text="Start", command=self.toggle_connection)
        self.start_button.pack(pady=10)
        self.status_label = ttk.Label(self.root, text="Status: Disconnected")
        self.status_label.pack()

    def toggle_connection(self):
        if not self.is_running:
            self.is_running = True
            self.status_label.config(text="Status: Connected")
            self.start_button.config(text="Stop")
            if not self.use_raw_input:
                self.start_screen_listener()  # fallback only if raw input is not available
        else:
            self.is_running = False
            self.status_label.config(text="Status: Disconnected")
            self.start_button.config(text="Start")

    def start_screen_listener(self):
        def on_move(x, y):
            # Prevent fight with raw input updates
            pass

        def on_click(x, y, button, pressed):
            pass

        def on_scroll(x, y, dx, dy):
            pass

        def run_listener():
            with mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll, suppress=True) as listener:
                while self.is_running:
                    time.sleep(0.01)

        threading.Thread(target=run_listener, daemon=True).start()

if __name__ == '__main__':
    root = tk.Tk()
    app = MouseSyncApp(root)
    root.mainloop()
