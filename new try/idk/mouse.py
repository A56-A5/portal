import socket
import threading
import time
import sys
import platform

# Server configuration
SERVER_IP = "192.168.1.71"  # Windows machine
CLIENT_IP = "192.168.1.74"  # Linux machine
PORT = 5000

# Platform-specific imports and functions
if platform.system() == "Windows":
    import win32api
    import win32con
    import ctypes
    from ctypes import wintypes, CFUNCTYPE, POINTER, c_int, c_void_p, byref
    
    # Windows hook structures
    class MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("pt", wintypes.POINT),
            ("mouseData", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", c_void_p)
        ]

    # Global variables for the hook
    mouse_dx = 0
    mouse_dy = 0
    client_socket = None

    # Mouse hook callback
    def mouse_hook_proc(nCode, wParam, lParam):
        global mouse_dx, mouse_dy, client_socket
        if nCode >= 0:
            if wParam == win32con.WM_MOUSEMOVE:
                ms = ctypes.cast(lParam, POINTER(MSLLHOOKSTRUCT)).contents
                mouse_dx = ms.pt.x
                mouse_dy = ms.pt.y
                if client_socket:
                    try:
                        data = f"{mouse_dx},{mouse_dy}\n"
                        client_socket.send(data.encode())
                    except:
                        pass
        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

    # Convert the callback to a C function
    HOOKPROC = CFUNCTYPE(c_int, c_int, wintypes.WPARAM, wintypes.LPARAM)
    mouse_hook = HOOKPROC(mouse_hook_proc)

    def install_mouse_hook():
        """Install the mouse hook"""
        hook_id = ctypes.windll.user32.SetWindowsHookExA(
            win32con.WH_MOUSE_LL,
            mouse_hook,
            ctypes.windll.kernel32.GetModuleHandleW(None),
            0
        )
        return hook_id

    def uninstall_mouse_hook(hook_id):
        """Uninstall the mouse hook"""
        ctypes.windll.user32.UnhookWindowsHookEx(hook_id)

elif platform.system() == "Linux":
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
        
        current_pos = get_mouse_position()
        buffer = ""
        
        while True:
            data = client_socket.recv(1024).decode()
            if data:
                buffer += data
                # Process complete messages
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    try:
                        dx, dy = map(int, message.split(','))
                        # Update current position with delta
                        current_pos = (current_pos[0] + dx, current_pos[1] + dy)
                        set_mouse_position(current_pos[0], current_pos[1])
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
