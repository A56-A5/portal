import socket
import struct
import time
from pynput.mouse import Controller

def start_server(host='0.0.0.0', port=5000):
    mouse = Controller()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(1)
    print(f"Server listening on {host}:{port}")

    conn, addr = server.accept()
    print(f"Client connected: {addr}")

    try:
        while True:
            x, y = mouse.position
            data = struct.pack('!ii', x, y)
            conn.sendall(data)
            time.sleep(0.01)  # 100 updates per second
    except (BrokenPipeError, ConnectionResetError):
        print("Client disconnected")
    except Exception as e:
        print("Server error:", e)
    finally:
        conn.close()
        server.close()

if __name__ == "__main__":
    start_server()
