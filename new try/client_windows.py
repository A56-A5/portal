import socket
import struct
import ctypes

def set_cursor_pos(x, y):
    ctypes.windll.user32.SetCursorPos(x, y)

def start_client(server_ip):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, 5000))
    print("Connected to server.")
    
    try:
        while True:
            data = sock.recv(8)  # 2 integers: x, y
            if not data:
                break
            x, y = struct.unpack('!ii', data)
            set_cursor_pos(x, y)
    except:
        print("Disconnected from server.")
    finally:
        sock.close()

if __name__ == "__main__":
    start_client("192.168.1.x")  # Replace with actual server IP
