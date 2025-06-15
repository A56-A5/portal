# invis.py
import sys
import socket
import threading
import json
import time
import platform
import pyperclip
from pynput import mouse,keyboard
from pynput.keyboard import Controller as KeyboardController, Key  
from pynput.mouse import Button, Controller
from config import app_config

class MouseSyncApp:
    def __init__(self):
        self.edge_transition_cooldown = False
        self.port = 50007
        self.mouse_controller = Controller()
        self.keyboard_controller = KeyboardController()
        self.server_socket = None
        self.client_socket = None
        self.overlay = None
        self.screen_width = None
        self.screen_height = None
        self.gui_app = None
        self.last_clipboard = pyperclip.paste()
        self.os_type = platform.system().lower()

        app_config.load()
        app_config.active_device = False

        if self.os_type == "windows":
            import tkinter as tk
            self.tk = tk
            self.gui_app = self.tk.Tk()
            self.gui_app.withdraw()
            self.screen_width = self.gui_app.winfo_screenwidth()
            self.screen_height = self.gui_app.winfo_screenheight()
        elif self.os_type == "linux":
            from PyQt5.QtWidgets import QApplication, QWidget
            from PyQt5.QtCore import Qt
            self.Qt = Qt
            self.QWidget = QWidget
            self.gui_app = QApplication(sys.argv)
            screen = self.gui_app.primaryScreen().size()
            self.screen_width = screen.width()
            self.screen_height = screen.height()

    def cleanup(self):
        print("[System] Cleaning up sockets and resources...")
        try:
            if self.client_socket:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
        except Exception as e:
            print(f"[Client] Error closing socket: {e}")
        try:
            if self.server_socket:
                self.server_socket.close()
        except Exception as e:
            print(f"[Server] Error closing socket: {e}")
        if self.overlay:
            self.destroy_overlay()

    def create_overlay(self):
        if not app_config.active_device:
            return
        if self.os_type == "windows":
            overlay = self.tk.Toplevel(self.gui_app)
            overlay.overrideredirect(True)
            overlay.attributes("-topmost", True)
            overlay.geometry(f"{self.screen_width}x{self.screen_height}+0+0")
            overlay.attributes("-alpha", 0.01)
            overlay.configure(bg="black")
            overlay.config(cursor="none")
            overlay.lift()
            overlay.focus_force()
            overlay.update_idletasks()
            self.overlay = overlay
        elif self.os_type == "linux":
            overlay = self.QWidget()
            overlay.setWindowFlags(self.Qt.FramelessWindowHint | self.Qt.WindowStaysOnTopHint | self.Qt.Tool)
            overlay.setAttribute(self.Qt.WA_TranslucentBackground)
            overlay.setCursor(self.Qt.BlankCursor)
            overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
            overlay.setWindowOpacity(0.0)
            overlay.show()
            overlay.raise_()
            self.overlay = overlay

    def destroy_overlay(self):
        if self.overlay:
            if self.os_type == "windows":
                self.overlay.destroy()
            elif self.os_type == "linux":
                self.overlay.close()
            self.overlay = None

    def monitor_mouse_edges(self):
        margin = 2
        while app_config.is_running:
            x, y = self.mouse_controller.position
            if not app_config.active_device and not self.edge_transition_cooldown:
                if app_config.server_direction == "Right" and x >= self.screen_width - margin:
                    self.transition(True, (margin, y))
                elif app_config.server_direction == "Left" and x <= margin:
                    self.transition(True, (self.screen_width - margin, y))
                elif app_config.server_direction == "Top" and y <= margin:
                    self.transition(True, (x, self.screen_height - margin))
                elif app_config.server_direction == "Bottom" and y >= self.screen_height - margin:
                    self.transition(True, (x, margin))
            elif app_config.active_device and not self.edge_transition_cooldown:
                if app_config.server_direction == "Right" and x <= margin:
                    self.transition(False, (self.screen_width - margin, y))
                elif app_config.server_direction == "Left" and x >= self.screen_width - margin:
                    self.transition(False, (margin, y))
                elif app_config.server_direction == "Top" and y >= self.screen_height - margin:
                    self.transition(False, (x, margin))
                elif app_config.server_direction == "Bottom" and y <= margin:
                    self.transition(False, (x, self.screen_height - margin))

            # Cooldown Reset
            if margin < x < self.screen_width - margin and margin < y < self.screen_height - margin:
                self.edge_transition_cooldown = False

            time.sleep(0.01)

    def transition(self, to_active, new_position):
        app_config.active_device = to_active
        self.edge_transition_cooldown = True
        if self.os_type == "windows":
            self.gui_app.after(0, self.create_overlay if to_active else self.destroy_overlay)
            self.gui_app.after(5, lambda: setattr(self.mouse_controller, 'position', new_position))
        else:
            if to_active:
                self.create_overlay()
            else:
                self.destroy_overlay()
            self.mouse_controller.position = new_position
        print(f"[System] Device {'Activated' if to_active else 'Deactivated'} at {new_position}")
        app_config.save()

    def input_sender(self, client_socket):
        def send_json(data):
            try:
                client_socket.sendall((json.dumps(data) + "\n").encode())
            except Exception as e:
                print(f"[Sender] Send failed: {e}")

        def on_move(x, y):
            if not app_config.active_device:
                return
            norm_x = x / self.screen_width
            norm_y = y / self.screen_height
            send_json({"type": "move", "x": norm_x, "y": norm_y})

        def on_click(x, y, button, pressed):
            if not app_config.active_device:
                return
            send_json({"type": "click", "button": button.name, "pressed": pressed})

        def on_scroll(x, y, dx, dy):
            if not app_config.active_device:
                return
            send_json({"type": "scroll", "dx": dx, "dy": dy})
        
        def on_press(key):
            if not app_config.active_device:
                return
            try:
                send_json({"type": "key_press", "key": key.char})
            except AttributeError:
                send_json({"type": "key_press", "key": str(key)})

        def on_release(key):
            if not app_config.active_device:
                return
            try:
                send_json({"type": "key_release", "key": key.char})
            except AttributeError:
                send_json({"type": "key_release", "key": str(key)})

        mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll).start()
        keyboard.Listener(on_press= on_press, on_release= on_release , suppress=True).start()
    def clipboard_monitor(self):
        while app_config.is_running:
            try:
                current_clipboard = pyperclip.paste()
                if current_clipboard != self.last_clipboard:
                    print("[Clipboard] Detected change in clipboard content")
                    self.last_clipboard = current_clipboard
                    app_config.clipboard = current_clipboard
                    app_config.save()

                app_config.load()
                if app_config.clipboard != self.last_clipboard:
                    print("[Clipboard] Remote change detected, updating local clipboard")
                    self.last_clipboard = app_config.clipboard
                    pyperclip.copy(self.last_clipboard)
            except Exception as e:
                print(f"[Clipboard] Error: {e}")
            time.sleep(0.5)
    def handle_client(self, client_socket):
        threading.Thread(target=self.monitor_mouse_edges, daemon=True).start()
        threading.Thread(target=self.input_sender, args=(client_socket,), daemon=True).start()
        threading.Thread(target=self.clipboard_monitor, daemon=True).start()

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.port))
        self.server_socket.listen(1)
        print(f"[Server] Listening on port {self.port}")

        def accept_client():
            client, addr = self.server_socket.accept()
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"[Server] Client connected: {addr}")
            client.sendall(b'CONNECTED\n')
            self.handle_client(client)

        threading.Thread(target=accept_client, daemon=True).start()

    def start_client(self):
        print(f"[Client] Connecting to {app_config.server_ip}:{self.port}")
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            self.client_socket.connect((app_config.server_ip, self.port))
            if self.client_socket.recv(1024) != b'CONNECTED\n':
                raise Exception("Handshake failed")
            print("[Client] Connected successfully.")

            def receive_thread():
                buffer = ""
                while app_config.is_running:
                    try:
                        data = self.client_socket.recv(1024).decode()
                    except Exception as e:
                        print(f"[Client] Receive error: {e}")
                        app_config.is_running = False
                        self.cleanup()
                        break
                    if not data:
                        break
                    buffer += data
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        try:
                            evt = json.loads(line)
                            if evt["type"] == "move":
                                x = int(evt["x"] * self.screen_width)
                                y = int(evt["y"] * self.screen_height)
                                self.mouse_controller.position = (x, y)
                            elif evt["type"] == "click":
                                btn = getattr(Button, evt['button'])
                                if evt['pressed']:
                                    self.mouse_controller.press(btn)
                                else:
                                    self.mouse_controller.release(btn)
                            elif evt["type"] == "scroll":
                                self.mouse_controller.scroll(evt['dx'], evt['dy'])
                            elif evt["type"] == "key_press":
                                key = getattr(Key, evt["key"].replace("Key.", "")) if "Key." in evt["key"] else evt["key"]
                                self.keyboard_controller.press(key)

                            elif evt["type"] == "key_release":
                                key = getattr(Key, evt["key"].replace("Key.", "")) if "Key." in evt["key"] else evt["key"]
                                self.keyboard_controller.release(key)
                        except Exception as e:
                            print(f"[Client] Parse error: {e}")
            threading.Thread(target=self.clipboard_monitor, daemon=True).start()
            threading.Thread(target=receive_thread, daemon=True).start()
        except Exception as e:
            print(f"[Client] Connection failed: {e}")

    def run(self):
        app_config.is_running = True
        if app_config.mode == "server":
            self.start_server()
        else:
            self.start_client()

        def monitor_stop():
            while app_config.is_running and not app_config.stop_flag:
                time.sleep(0.5)
            self.cleanup()
            self.gui_app.quit()

        threading.Thread(target=monitor_stop, daemon=True).start()

        if self.os_type == "windows":
            self.gui_app.mainloop()
        else:
            self.gui_app.exec_()

if __name__ == "__main__":
    MouseSyncApp().run()
