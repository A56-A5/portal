### client/client_mouse.py

import socket
import pyautogui
import sys

server_ip = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
PORT = 5000

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((server_ip, PORT))
    print("Connected to server")
    while True:
        data = s.recv(1024).decode()
        if not data:
            break
        x, y = map(int, data.split(","))
        pyautogui.moveTo(1, y)  # Simulate appearance on left edge