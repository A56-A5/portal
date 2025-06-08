# server.py
import socket
from config import app_config

def run_server():
    host = '0.0.0.0'
    port = 9999

    print(f"[SERVER] Starting on {host}:{port}...")
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(1)
        s.settimeout(1.0)  # Allow periodic checking for stop
        print("[SERVER] Waiting for a connection...")

        try:
            while not app_config.stop_flag:
                try:
                    conn, addr = s.accept()
                except socket.timeout:
                    continue

                with conn:
                    print(f"[SERVER] Connected by {addr}")
                    conn.settimeout(1.0)
                    while not app_config.stop_flag:
                        try:
                            data = conn.recv(1024)
                            if not data:
                                break
                            print("[SERVER] Received:", data.decode())
                            conn.sendall(b"ACK from server")
                        except socket.timeout:
                            continue
        except Exception as e:
            print("[SERVER] Exception:", e)

    print("[SERVER] Shutdown complete.")
