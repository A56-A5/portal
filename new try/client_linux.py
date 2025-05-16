import socket
import struct
import subprocess

def set_cursor_pos(x, y):
    subprocess.call(['xdotool', 'mousemove', str(x), str(y)])

def recv_all(sock, length):
    data = b''
    while len(data) < length:
        packet = sock.recv(length - len(data))
        if not packet:
            return None
        data += packet
    return data

def start_client(server_ip, port=5000):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, port))
    print("Connected to server:", server_ip)

    try:
        while True:
            data = recv_all(sock, 8)
            if data is None:
                print("Server closed connection.")
                break
            x, y = struct.unpack('!ii', data)
            set_cursor_pos(x, y)
    except Exception as e:
        print("Client error:", e)
    finally:
        sock.close()

if __name__ == "__main__":
    start_client("192.168.1.x")  # Replace with your server IP
