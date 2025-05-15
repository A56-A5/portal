# net/network.py
import socket
import threading

class NetworkConnection:
    def __init__(self, conn):
        self.conn = conn

    def send(self, data: bytes):
        self.conn.sendall(data)

    def receive(self, bufsize=4096) -> bytes:
        return self.conn.recv(bufsize)

    def close(self):
        self.conn.close()
