
### client/client_mouse.py

import socket
import pyautogui
import sys
import threading
import time

server_ip = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
PORT = 5000

def receive_messages(sock):
    screen_w, screen_h = pyautogui.size()
    while True:
        data = sock.recv(1024).decode()
        if not data:
            break
        parts = data.strip().split(',')
        if parts[0] == "TAKE_CONTROL":
            y = int(parts[1])
            pyautogui.moveTo(1, y)  # Appear at left edge

            while True:
                x, y = pyautogui.position()
                if x >= screen_w - 1:
                    sock.sendall(b"RETURN_CONTROL")
                    break
                time.sleep(0.01)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((server_ip, PORT))
    print("Connected to server")
    receive_messages(s)