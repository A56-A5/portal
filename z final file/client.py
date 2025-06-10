# client.py
import socket
from config import app_config

def run_client():
    host = app_config.client_ip or '127.0.0.1'
    port = 9999

    print(f"[CLIENT] Connecting to {host}:{port}...")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)  # Allow checking the stop_flag
            s.connect((host, port))
            print("[CLIENT] Connected to server.")

            while not app_config.stop_flag:
                try:
                    continue
                except socket.timeout:
                    continue
    except Exception as e:
        print(f"[CLIENT] Connection error: {e}")

    print("[CLIENT] Shutdown complete.")
