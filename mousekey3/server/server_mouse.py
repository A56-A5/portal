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
has_control = True


def accept_client():
    global client_conn
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen(1)
        print("Waiting for client...")
        client_conn, _ = s.accept()
        print("Client connected")
        listen_for_return(client_conn)


def listen_for_return(conn):
    global has_control
    def loop():
        while True:
            try:
                data = conn.recv(1024).decode()
                if data.strip() == "RETURN_CONTROL":
                    has_control = True
                    print("Server regained control")
            except:
                break
    threading.Thread(target=loop, daemon=True).start()


def send_mouse_control():
    global has_control
    screen_w, screen_h = pyautogui.size()
    while True:
        if has_control:
            x, y = pyautogui.position()
            if position == "right" and x >= screen_w - 1:
                client_conn.sendall(f"TAKE_CONTROL,{y}".encode())
                has_control = False
                pyautogui.moveTo(screen_w - 1, y)  # Pin mouse
        time.sleep(0.01)


threading.Thread(target=accept_client).start()

# Wait for client to connect
while client_conn is None:
    time.sleep(0.1)

send_mouse_control()