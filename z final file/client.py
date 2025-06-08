# client.py
import socket
from config import app_config

def run_client():
    host = app_config.client_ip or '127.0.0.1'
    port = 9999

    print(f"[CLIENT] Connecting to {host}:{port}...")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((host, port))
            print("[CLIENT] Connected to server.")

            while True:
                msg = input("Enter message (or 'exit'): ")
                if msg.lower() == "exit":
                    break
                s.sendall(msg.encode())
                data = s.recv(1024)
                print("[CLIENT] Received:", data.decode())
        except Exception as e:
            print(f"[CLIENT] Connection failed: {e}")

if __name__ == "__main__":
    if app_config.mode == "client":
        run_client()
    else:
        print("Not in client mode. Please switch to client mode in the UI.")


