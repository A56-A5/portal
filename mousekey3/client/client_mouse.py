### client/client_mouse.py

import socket
import pyautogui
import sys
import threading
import time

server_ip = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
PORT = 5000

has_control = False


def receive_mouse_data(sock):
    global has_control
    while True:
        data = sock.recv(1024).decode()
        if not data:
            break
        parts = data.strip().split(',')
        if parts[0] == "TAKE":
            has_control = True
            _, x, y = parts
            pyautogui.moveTo(1, int(y))

            # Client gets control and loops until mouse leaves left edge
            screen_w, screen_h = pyautogui.size()
            while has_control:
                x, y = pyautogui.position()
                if x <= 0:
                    has_control = False
                    break
                time.sleep(0.01)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((server_ip, PORT))
    print("Connected to server")
    receive_mouse_data(s)
