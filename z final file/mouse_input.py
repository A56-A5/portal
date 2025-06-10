# mouse_input.py
from pynput.mouse import Controller
import time

def monitor_mouse():
    mouse = Controller()
    while True:
        pos = mouse.position
        print(f"Mouse position: {pos}")
        time.sleep(0.1)
