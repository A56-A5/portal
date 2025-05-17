import tkinter as tk
from tkinter import ttk
import platform
import threading
import time
import os

# Platform-specific imports
if platform.system() == "Windows":
    import ctypes
    from ctypes import wintypes
    import win32api
    import win32con
    
    # Windows API structures for raw input
    class RAWINPUTDEVICE(ctypes.Structure):
        _fields_ = [
            ("usUsagePage", ctypes.c_ushort),
            ("usUsage", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("hwndTarget", ctypes.c_void_p)
        ]

    class RAWINPUTHEADER(ctypes.Structure):
        _fields_ = [
            ("dwType", ctypes.c_ulong),
            ("dwSize", ctypes.c_ulong),
            ("hDevice", ctypes.c_void_p),
            ("wParam", ctypes.c_void_p)
        ]

    class RAWMOUSE(ctypes.Structure):
        _fields_ = [
            ("usFlags", ctypes.c_ushort),
            ("usButtonFlags", ctypes.c_ushort),
            ("usButtonData", ctypes.c_ushort),
            ("ulRawButtons", ctypes.c_ulong),
            ("lLastX", ctypes.c_long),
            ("lLastY", ctypes.c_long),
            ("ulExtraInformation", ctypes.c_ulong)
        ]

    class RAWINPUT(ctypes.Structure):
        _fields_ = [
            ("header", RAWINPUTHEADER),
            ("mouse", RAWMOUSE)
        ]

    # Windows constants
    RIM_TYPEMOUSE = 0
    RIDEV_INPUTSINK = 0x00000100
    RID_INPUT = 0x10000003
    MOUSE_MOVE_RELATIVE = 0x00
    MOUSE_MOVE_ABSOLUTE = 0x01

elif platform.system() == "Linux":
    import Xlib
    from Xlib import X, display
    from Xlib.ext import record
    from Xlib.protocol import rq

class MonitorSync:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Monitor Sync")
        self.root.geometry("300x150")
        
        # Get screen dimensions
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        # Variables
        self.is_running = False
        self.original_cursor_pos = None
        
        # Platform-specific variables
        if platform.system() == "Windows":
            self.raw_input_handle = None
        elif platform.system() == "Linux":
            self.display = display.Display()
            self.record_display = display.Display()
            self.ctx = None
        
        # Setup GUI
        self.setup_gui()
        
        # Setup raw input
        self.setup_raw_input()
        
    def setup_gui(self):
        # Control button
        self.start_button = ttk.Button(self.root, text="Start", command=self.toggle_sync)
        self.start_button.pack(pady=20)
        
        # Status label
        self.status_label = ttk.Label(self.root, text="Status: Stopped")
        self.status_label.pack(pady=10)
        
    def setup_raw_input(self):
        if platform.system() == "Windows":
            # Register for raw input
            rid = RAWINPUTDEVICE()
            rid.usUsagePage = 0x01  # HID_USAGE_PAGE_GENERIC
            rid.usUsage = 0x02      # HID_USAGE_GENERIC_MOUSE
            rid.dwFlags = RIDEV_INPUTSINK
            rid.hwndTarget = self.root.winfo_id()
            
            if not ctypes.windll.user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
                raise Exception("Failed to register raw input device")
                
        elif platform.system() == "Linux":
            # Setup X11 record extension
            self.ctx = self.record_display.record_create_context(
                0,
                [record.AllClients],
                [{
                    'core_requests': (0, 0),
                    'core_replies': (0, 0),
                    'ext_requests': (0, 0, 0, 0),
                    'ext_replies': (0, 0, 0, 0),
                    'delivered_events': (0, 0),
                    'device_events': (X.MotionNotify, X.ButtonPress),
                    'errors': (0, 0),
                    'client_started': True,
                    'client_died': False,
                }]
            )
            
    def toggle_sync(self):
        if not self.is_running:
            self.start_sync()
        else:
            self.stop_sync()
            
    def start_sync(self):
        try:
            # Store original cursor position
            if platform.system() == "Windows":
                self.original_cursor_pos = win32api.GetCursorPos()
                ctypes.windll.user32.ShowCursor(False)
            elif platform.system() == "Linux":
                self.original_cursor_pos = self.display.screen().root.query_pointer()._data
                os.system("xsetroot -cursor_name none")
            
            # Start raw input processing
            self.is_running = True
            self.start_button.config(text="Stop")
            self.status_label.config(text="Status: Running")
            
            # Start processing thread
            threading.Thread(target=self.process_raw_input, daemon=True).start()
            
        except Exception as e:
            print(f"Error starting sync: {e}")
            self.stop_sync()
            
    def stop_sync(self):
        self.is_running = False
        
        # Show cursor
        if platform.system() == "Windows":
            ctypes.windll.user32.ShowCursor(True)
            if self.original_cursor_pos:
                win32api.SetCursorPos(self.original_cursor_pos)
        elif platform.system() == "Linux":
            os.system("xsetroot -cursor_name left_ptr")
            if self.original_cursor_pos:
                self.display.screen().root.warp_pointer(
                    self.original_cursor_pos["root_x"],
                    self.original_cursor_pos["root_y"]
                )
            
        self.start_button.config(text="Start")
        self.status_label.config(text="Status: Stopped")
        
    def process_raw_input(self):
        if platform.system() == "Windows":
            self.process_windows_raw_input()
        elif platform.system() == "Linux":
            self.process_linux_raw_input()
            
    def process_windows_raw_input(self):
        while self.is_running:
            try:
                # Get raw input data
                size = ctypes.c_ulong()
                ctypes.windll.user32.GetRawInputData(
                    self.raw_input_handle,
                    RID_INPUT,
                    None,
                    ctypes.byref(size),
                    ctypes.sizeof(RAWINPUTHEADER)
                )
                
                if size.value > 0:
                    buffer = ctypes.create_string_buffer(size.value)
                    ctypes.windll.user32.GetRawInputData(
                        self.raw_input_handle,
                        RID_INPUT,
                        buffer,
                        ctypes.byref(size),
                        ctypes.sizeof(RAWINPUTHEADER)
                    )
                    
                    raw_input = RAWINPUT.from_buffer(buffer)
                    
                    if raw_input.header.dwType == RIM_TYPEMOUSE:
                        # Get current cursor position
                        current_pos = win32api.GetCursorPos()
                        
                        # Calculate new position based on raw input
                        new_x = current_pos[0] + raw_input.mouse.lLastX
                        new_y = current_pos[1] + raw_input.mouse.lLastY
                        
                        # Clamp to screen boundaries
                        new_x = max(0, min(new_x, self.screen_width - 1))
                        new_y = max(0, min(new_y, self.screen_height - 1))
                        
                        # Move cursor to new position
                        win32api.SetCursorPos((new_x, new_y))
                        
                        # Reset to original position to keep it in place
                        if self.original_cursor_pos:
                            win32api.SetCursorPos(self.original_cursor_pos)
                            
            except Exception as e:
                print(f"Error processing raw input: {e}")
                time.sleep(0.01)
                
    def process_linux_raw_input(self):
        self.record_display.record_enable_context(self.ctx, self.raw_event_callback)
        self.record_display.record_free_context(self.ctx)
        
    def raw_event_callback(self, reply):
        if not self.is_running:
            return
            
        if reply.category != record.FromServer:
            return
            
        if reply.client_swapped:
            return
            
        if not len(reply.data) or reply.data[0] < 2:
            return
            
        data = reply.data
        while len(data):
            event, data = rq.EventField(None).parse_binary_value(data, self.record_display.display, None, None)
            
            if event.type == X.MotionNotify:
                # Get current cursor position
                current_pos = self.display.screen().root.query_pointer()._data
                
                # Calculate new position based on relative movement
                new_x = current_pos["root_x"] + event.root_x
                new_y = current_pos["root_y"] + event.root_y
                
                # Clamp to screen boundaries
                new_x = max(0, min(new_x, self.screen_width - 1))
                new_y = max(0, min(new_y, self.screen_height - 1))
                
                # Move cursor to new position
                self.display.screen().root.warp_pointer(new_x, new_y)
                
                # Reset to original position to keep it in place
                if self.original_cursor_pos:
                    self.display.screen().root.warp_pointer(
                        self.original_cursor_pos["root_x"],
                        self.original_cursor_pos["root_y"]
                    )
                    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
        
    def on_closing(self):
        self.stop_sync()
        self.root.destroy()

if __name__ == "__main__":
    app = MonitorSync()
    app.run()
