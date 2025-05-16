# net/network.py
import socket
import threading
import json

class NetworkConnection:
    def __init__(self, conn):
        self.conn = conn

    def send(self, data):
        if isinstance(data, dict):
            data = json.dumps(data) + '\n'  # Add newline to separate JSON objects
            data = data.encode('utf-8')
        self.conn.sendall(data)

    def receive(self, bufsize=4096) -> bytes:
        return self.conn.recv(bufsize)

    def close(self):
        self.conn.close()
