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
            # Calculate delta movement
            dx = current_pos[0] - last_pos[0]
            dy = current_pos[1] - last_pos[1]
            
            if dx != 0 or dy != 0:
                # Send delta movement to client with newline to separate messages
                data = f"{dx},{dy}\n"
                client_socket.send(data.encode())
                last_pos = current_pos
            time.sleep(0.01)  # Small delay to prevent high CPU usage
    except Exception as e:
        print(f"Server error: {e}")
    finally:
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
