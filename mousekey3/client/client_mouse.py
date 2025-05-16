### client/client_mouse.py

import socket
import pyautogui
import sys
import threading
import time

server_ip = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
PORT = 5000

def receive_deltas(sock):
    screen_w, screen_h = pyautogui.size()
    while True:
        try:
            data = sock.recv(1024).decode()
            if not data:
                break
            parts = data.strip().split(',')
            if parts[0] == "MOVE":
                dx = int(parts[1])
                dy = int(parts[2])
                pyautogui.moveRel(dx, dy)

                x, y = pyautogui.position()
                if x <= 0 or x >= screen_w - 1 or y <= 0 or y >= screen_h - 1:
                    sock.sendall(b"RETURN_CONTROL")
        except:
            break

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((server_ip, PORT))
    print("Connected to server")
    receive_deltas(s)