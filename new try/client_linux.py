import socket
import struct
import subprocess

def set_cursor_pos(x, y):
    subprocess.call(['xdotool', 'mousemove', str(x), str(y)])

def start_client(server_ip):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, 5000))
    print("Connected to server.")
    
    try:
        while True:
            data = sock.recv(8)
            if not data:
                break
            x, y = struct.unpack('!ii', data)
            set_cursor_pos(x, y)
    except:
        print("Disconnected.")
    finally:
        sock.close()

if __name__ == "__main__":
    start_client("192.168.1.x")  # Replace with actual server IP
