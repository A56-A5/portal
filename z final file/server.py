# server.py
import socket
import threading
import time
from config import app_config
from mouse_input import monitor_mouse

def handle_client(addr):
    monitor_mouse()

def run_server():
    host = '0.0.0.0'
    port = 9999

    print(f"[SERVER] Starting on {host}:{port}...")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen(1)
        s.settimeout(1.0)
        print("[SERVER] Waiting for a connection...")

        try:
            while not app_config.stop_flag:
                try:
                    conn, addr = s.accept()
                    print(f"[SERVER] Connected by {addr}")

                    # Start monitor_mouse in a new thread
                    thread = threading.Thread(target=handle_client, daemon = True,args=(addr,))
                    thread.start()

                    conn.close()
                except socket.timeout:
                    time.sleep(0.1)
                    continue
        except Exception as e:
            print("[SERVER] Exception:", e)

    print("[SERVER] Shutdown initiated.")
    print("[SERVER] Shutdown complete.")
