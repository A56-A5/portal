import socket
import threading
import time
import sys
import platform
import ctypes
from ctypes import wintypes, CFUNCTYPE, POINTER, c_int, c_void_p, byref

# Server configuration
SERVER_IP = "192.168.1.71"  # Windows machine
CLIENT_IP = "192.168.1.74"  # Linux machine
PORT = 5000

# Windows constants
WH_MOUSE_LL = 14
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_MOUSEHWHEEL = 0x020E

# Windows structures
class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", c_void_p)
    ]

# Global variables
client_socket = None
screen_x = 0
screen_y = 0
screen_w = 0
screen_h = 0
screen_center_x = 0
screen_center_y = 0

def get_screen_info():
    """Get screen dimensions and center"""
    global screen_x, screen_y, screen_w, screen_h, screen_center_x, screen_center_y
    user32 = ctypes.windll.user32
    screen_w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    screen_h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    screen_center_x = screen_w // 2
    screen_center_y = screen_h // 2

def warp_cursor_to_center():
    """Warp cursor to screen center"""
    ctypes.windll.user32.SetCursorPos(screen_center_x, screen_center_y)

# Mouse hook callback
def mouse_hook_proc(nCode, wParam, lParam):
    global client_socket
    
    if nCode >= 0:
        ms = ctypes.cast(lParam, POINTER(MSLLHOOKSTRUCT)).contents
        
        if client_socket:
            try:
                # Handle different types of events
                if wParam == WM_MOUSEMOVE:
                    # Send absolute position for movement
                    data = f"MOVE:{ms.pt.x},{ms.pt.y}\n"
                    client_socket.send(data.encode())
                    # Warp cursor back to center after sending
                    warp_cursor_to_center()
                elif wParam in (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN):
                    # Send button down events
                    data = f"DOWN:{wParam}\n"
                    client_socket.send(data.encode())
                elif wParam in (WM_LBUTTONUP, WM_RBUTTONUP, WM_MBUTTONUP):
                    # Send button up events
                    data = f"UP:{wParam}\n"
                    client_socket.send(data.encode())
                elif wParam in (WM_MOUSEWHEEL, WM_MOUSEHWHEEL):
                    # Send wheel events
                    wheel_data = ms.mouseData >> 16
                    data = f"WHEEL:{wheel_data}\n"
                    client_socket.send(data.encode())
            except:
                pass
    
    # Always pass the event through
    return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

# Convert the callback to a C function
HOOKPROC = CFUNCTYPE(c_int, c_int, wintypes.WPARAM, wintypes.LPARAM)
mouse_hook = HOOKPROC(mouse_hook_proc)

def install_mouse_hook():
    """Install the mouse hook"""
    hook_id = ctypes.windll.user32.SetWindowsHookExA(
        WH_MOUSE_LL,
        mouse_hook,
        ctypes.windll.kernel32.GetModuleHandleW(None),
        0
    )
    return hook_id

def uninstall_mouse_hook(hook_id):
    """Uninstall the mouse hook"""
    ctypes.windll.user32.UnhookWindowsHookEx(hook_id)

if platform.system() == "Linux":
    try:
        import Xlib.display
        display = Xlib.display.Display()
        root = display.screen().root
    except ImportError:
        print("Please install python-xlib: pip install python-xlib")
        sys.exit(1)
    
    def get_mouse_position():
        """Get current mouse position on Linux"""
        pos = root.query_pointer()._data
        return (pos["root_x"], pos["root_y"])
    
    def set_mouse_position(x, y):
        """Set mouse position on Linux"""
        root.warp_pointer(x, y)
        display.sync()

def server():
    """Server that captures mouse movements and sends them to client"""
    if platform.system() != "Windows":
        print("Server must run on Windows")
        sys.exit(1)
    
    global client_socket
    
    # Get screen info
    get_screen_info()
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((SERVER_IP, PORT))
    server_socket.listen(1)
    print(f"Server listening on {SERVER_IP}:{PORT}")
    
    client_socket, addr = server_socket.accept()
    print(f"Connected to client: {addr}")
    
    # Install the mouse hook
    hook_id = install_mouse_hook()
    
    try:
        # Message loop to keep the hook active
        msg = wintypes.MSG()
        while ctypes.windll.user32.GetMessageA(byref(msg), None, 0, 0) != 0:
            ctypes.windll.user32.TranslateMessage(byref(msg))
            ctypes.windll.user32.DispatchMessageA(byref(msg))
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        uninstall_mouse_hook(hook_id)
        client_socket.close()
        server_socket.close()

def client():
    """Client that receives mouse movements and updates local mouse"""
    if platform.system() != "Linux":
        print("Client must run on Linux")
        sys.exit(1)
        
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        client_socket.connect((SERVER_IP, PORT))
        print(f"Connected to server at {SERVER_IP}:{PORT}")
        
        buffer = ""
        
        while True:
            data = client_socket.recv(1024).decode()
            if data:
                buffer += data
                # Process complete messages
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    try:
                        msg_type, msg_data = message.split(':', 1)
                        
                        if msg_type == "MOVE":
                            # For movement, use absolute position
                            x, y = map(int, msg_data.split(','))
                            set_mouse_position(x, y)
                        elif msg_type == "DOWN":
                            # Handle button down
                            pass
                        elif msg_type == "UP":
                            # Handle button up
                            pass
                        elif msg_type == "WHEEL":
                            # Handle wheel
                            pass
                    except ValueError:
                        continue  # Skip invalid messages
    except Exception as e:
        print(f"Client error: {e}")
    finally:
        client_socket.close()

if __name__ == "__main__":
    print("\n=== Mouse Control Setup ===")
    print("1. Run as Server (Windows)")
    print("2. Run as Client (Linux)")
    print("3. Exit")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-3): ")
            
            if choice == "1":
                print("\nStarting server...")
                server()
            elif choice == "2":
                print("\nStarting client...")
                client()
            elif choice == "3":
                print("Exiting...")
                sys.exit(0)
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
        except KeyboardInterrupt:
            print("\nExiting...")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again.")
