import socket
import threading
import time
import struct
from pynput.mouse import Controller

mouse = Controller()

def send_mouse_positions(conn):
    try:
        while True:
            x, y = mouse.position
            data = struct.pack('!ii', x, y)  # Network byte order
            conn.sendall(data)
            time.sleep(0.01)  # 100 fps
    except:
        print("Client disconnected.")
        conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 5000))
    server.listen(1)
    print("Waiting for a client to connect...")
    conn, addr = server.accept()
    print(f"Client connected from {addr}")
    send_mouse_positions(conn)

if __name__ == "__main__":
    start_server()
