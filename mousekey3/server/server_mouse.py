### server/server_mouse.py

import socket
import pyautogui
import threading
import time
import sys

HOST = '0.0.0.0'
PORT = 5000
position = sys.argv[1] if len(sys.argv) > 1 else "right"

client_conn = None

def accept_client():
    global client_conn
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(1)
        print("Waiting for client...")
        client_conn, _ = s.accept()
        print("Client connected")

def send_mouse_position():
    global client_conn
    screen_w, screen_h = pyautogui.size()
    has_control = True
    while True:
        x, y = pyautogui.position()

        if has_control:
            if position == "right" and x >= screen_w - 1:
                has_control = False
                client_conn.sendall(f"TAKE,{x},{y}".encode())
                pyautogui.moveTo(screen_w - 2, y)  # Pin to edge

        time.sleep(0.01)

threading.Thread(target=accept_client).start()

while client_conn is None:
    time.sleep(0.1)

send_mouse_position()