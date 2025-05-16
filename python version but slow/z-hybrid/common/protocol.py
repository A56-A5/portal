import socket
import struct

PORT = 5005

def create_sender(ip):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    def send_mouse_delta(dx, dy):
        data = struct.pack("!ii", dx, dy)
        sock.sendto(data, (ip, PORT))
    return send_mouse_delta

def create_receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    return sock
