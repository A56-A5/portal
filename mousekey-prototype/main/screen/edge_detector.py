import time
import threading
import platform

if platform.system() == "Windows":
    import ctypes

    def get_mouse_position():
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def get_screen_size():
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

else:
    from Xlib import display

    def get_mouse_position():
        d = display.Display()
        coord = d.screen().root.query_pointer()._data
        return coord["root_x"], coord["root_y"]

    def get_screen_size():
        d = display.Display()
        screen = d.screen()
        return screen.width_in_pixels, screen.height_in_pixels

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
        screen_width, screen_height = get_screen_size()

        while self.running:
            x, y = get_mouse_position()
            if x <= 0:
                self.on_edge_callback("left")
            elif x >= screen_width - 1:
                self.on_edge_callback("right")
            elif y <= 0:
                self.on_edge_callback("top")
            elif y >= screen_height - 1:
                self.on_edge_callback("bottom")
            time.sleep(self.delay)
