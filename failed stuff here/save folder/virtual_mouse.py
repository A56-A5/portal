import tkinter as tk
from tkinter import ttk
import platform
import ctypes
from ctypes import windll, Structure, c_long, byref, c_uint, sizeof, POINTER, c_void_p, c_ulong, c_ushort, c_int
import win32api
import win32con
import win32gui

# Windows Raw Input structures
class RAWINPUTDEVICE(Structure):
    _fields_ = [
        ("usUsagePage", c_ushort),
        ("usUsage", c_ushort),
        ("dwFlags", c_ulong),
        ("hwndTarget", c_void_p)
    ]

class RAWINPUTHEADER(Structure):
    _fields_ = [
        ("dwType", c_ulong),
        ("dwSize", c_ulong),
        ("hDevice", c_void_p),
        ("wParam", c_void_p)
    ]

class RAWMOUSE(Structure):
    _fields_ = [
        ("usFlags", c_ushort),
        ("ulButtons", c_ulong),
        ("ulRawButtons", c_ulong),
        ("lLastX", c_long),
        ("lLastY", c_long),
        ("ulExtraInformation", c_ulong)
    ]

class RAWINPUT(Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", RAWMOUSE)
    ]

# Windows API constants
RIM_TYPEMOUSE = 0
RIDEV_INPUTSINK = 0x00000100
RIDEV_REMOVE = 0x00000001
WM_INPUT = 0x00FF
MOUSE_MOVE_RELATIVE = 0x00
MOUSE_MOVE_ABSOLUTE = 0x01

class VirtualMouseApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Virtual Mouse")
        self.root.geometry("200x100")
        
        # Get screen dimensions
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        # Virtual pointer position
        self.virtual_x = self.screen_width // 2
        self.virtual_y = self.screen_height // 2
        
        # Create virtual pointer window
        self.virtual_pointer = tk.Toplevel(self.root)
        self.virtual_pointer.overrideredirect(True)  # Remove window decorations
        self.virtual_pointer.attributes('-topmost', True)  # Keep on top
        self.virtual_pointer.attributes('-alpha', 0.8)  # Slight transparency
        
        # Create canvas for the red dot
        self.pointer_canvas = tk.Canvas(self.virtual_pointer, width=10, height=10, 
                                      bg='white', highlightthickness=0)
        self.pointer_canvas.pack()
        
        # Draw red dot
        self.pointer_canvas.create_oval(0, 0, 10, 10, fill='red', outline='red')
        
        # Setup raw input
        self.setup_raw_input()
        
        # Setup GUI
        self.setup_gui()
        
        # Initial position
        self.update_virtual_pointer(self.virtual_x, self.virtual_y)
        
    def setup_raw_input(self):
        """Setup raw input device for Windows"""
        try:
            # Register raw input device
            rid = RAWINPUTDEVICE()
            rid.usUsagePage = 0x01  # HID_USAGE_PAGE_GENERIC
            rid.usUsage = 0x02      # HID_USAGE_GENERIC_MOUSE
            rid.dwFlags = RIDEV_INPUTSINK
            rid.hwndTarget = self.root.winfo_id()
            
            if not windll.user32.RegisterRawInputDevices(byref(rid), 1, sizeof(rid)):
                print("Failed to register raw input device")
                
            # Bind raw input message
            self.root.bind('<Map>', lambda e: self.root.focus_force())
            self.root.bind('<FocusIn>', lambda e: self.root.focus_force())
            self.root.bind(WM_INPUT, self.handle_raw_input)
            
        except Exception as e:
            print(f"Error setting up raw input: {e}")
            
    def handle_raw_input(self, msg):
        """Handle raw input messages"""
        try:
            # Get raw input data
            dwSize = c_ulong(sizeof(RAWINPUT))
            windll.user32.GetRawInputData(
                msg.lParam,
                RIM_TYPEMOUSE,
                None,
                byref(dwSize),
                sizeof(RAWINPUTHEADER)
            )
            
            raw = RAWINPUT()
            windll.user32.GetRawInputData(
                msg.lParam,
                RIM_TYPEMOUSE,
                byref(raw),
                byref(dwSize),
                sizeof(RAWINPUTHEADER)
            )
            
            # Process relative movement
            if raw.data.usFlags == MOUSE_MOVE_RELATIVE:
                dx = raw.data.lLastX
                dy = raw.data.lLastY
                
                # Update virtual pointer position
                self.virtual_x += dx
                self.virtual_y += dy
                
                # Clamp to screen boundaries
                self.virtual_x = max(0, min(self.virtual_x, self.screen_width - 1))
                self.virtual_y = max(0, min(self.virtual_y, self.screen_height - 1))
                
                # Update visualization
                self.update_virtual_pointer(self.virtual_x, self.virtual_y)
                
                # Block the real mouse movement
                current_x, current_y = win32api.GetCursorPos()
                win32api.SetCursorPos((current_x - dx, current_y - dy))
                
        except Exception as e:
            print(f"Error handling raw input: {e}")
            
    def update_virtual_pointer(self, x, y):
        """Update the position of the virtual pointer dot"""
        self.virtual_pointer.geometry(f"+{x-5}+{y-5}")  # Center the dot
        self.virtual_pointer.deiconify()  # Show the pointer
        
    def setup_gui(self):
        # Control button
        self.toggle_button = ttk.Button(self.root, text="Start", command=self.toggle_mouse)
        self.toggle_button.pack(pady=10)
        
        # Status label
        self.status_label = ttk.Label(self.root, text="Status: Disabled")
        self.status_label.pack(pady=5)
        
    def toggle_mouse(self):
        if self.toggle_button.cget("text") == "Start":
            self.start_virtual_mouse()
        else:
            self.stop_virtual_mouse()
            
    def start_virtual_mouse(self):
        # Hide real cursor
        for _ in range(50):
            win32api.ShowCursor(False)
            
        # Block input at system level
        try:
            ctypes.windll.user32.BlockInput(True)
            ctypes.windll.user32.SystemParametersInfoW(0x101F, 0, None, 0x01 | 0x02)
            ctypes.windll.user32.SystemParametersInfoW(0x101D, 0, None, 0x01 | 0x02)
            ctypes.windll.user32.SystemParametersInfoW(0x1021, 0, None, 0x01 | 0x02)
        except:
            print("Could not block input")
            
        self.toggle_button.config(text="Stop")
        self.status_label.config(text="Status: Enabled")
        
    def stop_virtual_mouse(self):
        # Show real cursor
        for _ in range(50):
            win32api.ShowCursor(True)
            
        # Enable input at system level
        try:
            ctypes.windll.user32.BlockInput(False)
            ctypes.windll.user32.SystemParametersInfoW(0x101F, 1, None, 0x01 | 0x02)
            ctypes.windll.user32.SystemParametersInfoW(0x101D, 1, None, 0x01 | 0x02)
            ctypes.windll.user32.SystemParametersInfoW(0x1021, 1, None, 0x01 | 0x02)
        except:
            print("Could not enable input")
            
        self.toggle_button.config(text="Start")
        self.status_label.config(text="Status: Disabled")
        
    def on_closing(self):
        """Clean up when closing"""
        self.stop_virtual_mouse()
        self.virtual_pointer.destroy()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = VirtualMouseApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop() 