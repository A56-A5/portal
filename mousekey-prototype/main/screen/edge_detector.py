import pyautogui
import time
import threading

class EdgeMonitor:
    def __init__(self, on_edge_callback, delay=0.05):
        self.on_edge_callback = on_edge_callback
        self.running = False
        self.delay = delay

    def start(self):
        self.running = True
        threading.Thread(target=self._monitor, daemon=True).start()

    def stop(self):
        self.running = False

    def _monitor(self):
        screen_width, screen_height = pyautogui.size()

        while self.running:
            x, y = pyautogui.position()
            if x <= 0:
                self.on_edge_callback("left")
            elif x >= screen_width - 1:
                self.on_edge_callback("right")
            elif y <= 0:
                self.on_edge_callback("top")
            elif y >= screen_height - 1:
                self.on_edge_callback("bottom")
            time.sleep(self.delay)
