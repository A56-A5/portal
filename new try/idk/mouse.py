import socket
import threading
import win32api
import win32con
import time
import sys

# Server configuration
SERVER_IP = "192.168.1.71"
CLIENT_IP = "192.168.1.74"
PORT = 5000

def get_mouse_position():
    """Get current mouse position"""
    return win32api.GetCursorPos()

def set_mouse_position(x, y):
    """Set mouse position"""
    win32api.SetCursorPos((x, y))

def server():
    """Server that captures mouse movements and sends them to client"""
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
