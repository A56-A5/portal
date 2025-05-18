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
    
    def get_mouse_position():
        """Get current mouse position on Windows"""
        return win32api.GetCursorPos()
    
    def set_mouse_position(x, y):
        """Set mouse position on Windows"""
        win32api.SetCursorPos((x, y))

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
        
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((SERVER_IP, PORT))
    server_socket.listen(1)
    print(f"Server listening on {SERVER_IP}:{PORT}")
    
    client_socket, addr = server_socket.accept()
    print(f"Connected to client: {addr}")
    
    last_pos = get_mouse_position()
    
    try:
        while True:
            current_pos = get_mouse_position()
            if current_pos != last_pos:
                # Send mouse position to client
                data = f"{current_pos[0]},{current_pos[1]}"
                client_socket.send(data.encode())
                last_pos = current_pos
            time.sleep(0.01)  # Small delay to prevent high CPU usage
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        client_socket.close()
        server_socket.close()

def client():
    """Client that receives mouse positions and updates local mouse"""
    if platform.system() != "Linux":
        print("Client must run on Linux")
        sys.exit(1)
        
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        client_socket.connect((SERVER_IP, PORT))
        print(f"Connected to server at {SERVER_IP}:{PORT}")
        
        while True:
            data = client_socket.recv(1024).decode()
            if data:
                x, y = map(int, data.split(','))
                set_mouse_position(x, y)
    except Exception as e:
        print(f"Client error: {e}")
    finally:
        client_socket.close()

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ['server', 'client']:
        print("Usage: python mouse.py [server|client]")
        sys.exit(1)
    
    if sys.argv[1] == 'server':
        server()
    else:
        client()
