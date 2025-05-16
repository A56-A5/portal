import pyautogui
import time
from common.protocol import create_sender

EDGE_THRESHOLD = 2
screen_w, screen_h = pyautogui.size()
last_x, last_y = pyautogui.position()

def run_server(client_ip):
    send_delta = create_sender(client_ip)
    print(f"🟢 Server started for client {client_ip}")

    while True:
        x, y = pyautogui.position()
        dx = x - last_x
        dy = y - last_y
        if dx != 0 or dy != 0:
            if x <= EDGE_THRESHOLD or x >= screen_w - EDGE_THRESHOLD or \
               y <= EDGE_THRESHOLD or y >= screen_h - EDGE_THRESHOLD:
                send_delta(dx, dy)
        global last_x, last_y
        last_x, last_y = x, y
        time.sleep(0.01)
