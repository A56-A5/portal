# server.py
import socket
from config import app_config

def run_server():
    host = '0.0.0.0'
    port = 9999

    print(f"[SERVER] Starting on {host}:{port}...")
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen(1)
        print("[SERVER] Waiting for a connection...")

        conn, addr = s.accept()
        with conn:
            print(f"[SERVER] Connected by {addr}")
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                print("[SERVER] Received:", data.decode())
                conn.sendall(b"ACK from server")

if __name__ == "__main__":
    if app_config.mode == "server":
        run_server()
    else:
        print("Not in server mode. Please switch to server mode in the UI.")
