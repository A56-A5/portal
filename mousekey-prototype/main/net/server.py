# net/server.py
import socket
import threading
from net.network import NetworkConnection

class Server:
    def __init__(self, host='0.0.0.0', port=5051):
        self.host = host
        self.port = port
        self.connections = []

    def start(self, handle_client):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind((self.host, self.port))
        server_sock.listen(5)
        print(f"[Server] Listening on {self.host}:{self.port}")

        def accept_loop():
            while True:
                client_sock, addr = server_sock.accept()
                print(f"[Server] Connected to {addr}")
                conn = NetworkConnection(client_sock)
                self.connections.append(conn)
                threading.Thread(target=handle_client, args=(conn,), daemon=True).start()

        threading.Thread(target=accept_loop, daemon=True).start()
