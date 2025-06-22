# share.py
import sys
import socket
import threading
import json
import time
import platform
import pyperclip
import logging 
from pynput import mouse,keyboard
from pynput.keyboard import Controller as KeyboardController, Key  
from pynput.mouse import Button, Controller
from config import app_config

class MouseSyncApp:
    def __init__(self):
        self.edge_transition_cooldown = False
        self.primary_port = 50007
        self.secondary_port = 50008
        self.retry = 5
        self.mouse_controller = Controller()
        self.keyboard_controller = KeyboardController()
        self.keyboard_listener = None
        self.keyboard_listener_lock = threading.Lock()
        self.server_socket = None
        self.client_socket = None
        self.secondary_client_socket = None
        self.overlay = None
        self.screen_width = None
        self.screen_height = None
        self.gui_app = None
        self.last_send = pyperclip.paste()
        self.last_clipboard1 = pyperclip.paste()
        self.os_type = platform.system().lower()

        logging.basicConfig(level=logging.INFO, filename="logs.log", filemode="a",format ="%(levelname)s - %(message)s")

        app_config.load()
        app_config.active_device = False
        app_config.save()

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
        logging.info("[System] Closing all sockets")
        try:
            if self.client_socket:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
            if self.secondary_client_socket:
                self.secondary_client_socket.shutdown(socket.SHUT_RDWR)
                self.secondary_client_socket.close()
        except Exception as e:
            print(f"[Client] Error closing socket: {e}")
            logging.info(f"[Client] Error closing socket: {e}")
        try:
            if self.server_socket:
                self.server_socket.close()
        except Exception as e:
            print(f"[Server] Error closing socket: {e}")
            logging.info(f"[Server] Error closing socket: {e}")
        if self.overlay:
            self.destroy_overlay()
        app_config.is_running = False
        app_config.save()

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

    def monitor_mouse_edges(self,client_socket):
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
        try:
            import win32api 
        except:
            print("")
        app_config.load()
        app_config.active_device = to_active
        self.edge_transition_cooldown = True
        if self.os_type == "windows":
            self.gui_app.after(1, self.create_overlay if to_active else self.destroy_overlay)
            self.mouse_controller.position = new_position
            self.gui_app.after_idle(lambda: self.mouse_controller.position)  
        else:
            if to_active:
                self.create_overlay()
            else:
                self.destroy_overlay()
            if self.os_type == "linux":
                self.mouse_controller.position = new_position
            elif self.os_type == "windows":
                win32api.SetCursorPos(new_position)
                
        try:
            active_msg = {"type": "active_device", "value": to_active}
            self.secondary_server.sendall((json.dumps(active_msg) + "\n").encode())
        except Exception as e:
            print(f"[Transition] Failed to send active_device state: {e}")
            logging.info(f"[Transition] Failed to send active_device state: {e}")

        if to_active:
            try:
                if pyperclip.paste() != self.last_send:
                    self.last_send = app_config.clipboard
                    clipboard_msg = {"type": "clipboard", "content": app_config.clipboard}
                    self.secondary_server.sendall((json.dumps(clipboard_msg) + "\n").encode())
                    print("[Clipboard] Sent clipboard to client")
            except Exception as e:
                print(f"")

        
        print(f"[System] Device {'Activated' if to_active else 'Deactivated'} at {new_position}")
        logging.info(f"[System] Device {'Activated' if to_active else 'Deactivated'} at {new_position}")
        app_config.save()

    def input_sender_mouse(self, client_socket):
        def send_json(data):
            try:
                client_socket.sendall((json.dumps(data) + "\n").encode())
            except Exception as e:
                app_config.is_running = False
                app_config.save()
                print(f"[Server] Send failed: {e}")
                logging.info("[Server] Send failed: {e}")
    
        def on_move(x, y):
            if not app_config.active_device and app_config.is_running:
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

        mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll).start()

    def input_sender_keyboard(self, client_socket):
        def send_json(data):
            try:
                client_socket.sendall((json.dumps(data) + "\n").encode())
            except Exception as e:
                app_config.is_running = False
                app_config.save()
                print(f"[Server] Send failed: {e}")
                logging.info("[Server] Send failed: {e}")

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
    
        # Keyboard listener handler thread
        def keyboard_listener_watcher():
            while app_config.is_running:
                with self.keyboard_listener_lock:
                    if app_config.active_device and self.keyboard_listener is None:
                        self.keyboard_listener = keyboard.Listener(
                            on_press=on_press, on_release=on_release, suppress=True
                        )
                        self.keyboard_listener.start()
    
                    elif not app_config.active_device and self.keyboard_listener is not None:
                        self.keyboard_listener.stop()
                        self.keyboard_listener = None
                time.sleep(0.5)
    
        threading.Thread(target=keyboard_listener_watcher, daemon=True).start()
    
    def clipboard_monitor(self):
        while app_config.is_running:
            try:
                current_clipboard = pyperclip.paste()
                if current_clipboard != self.last_clipboard1:
                    self.last_clipboard1 = current_clipboard
                    app_config.clipboard = current_clipboard
                    app_config.save()
                
                app_config.load()
                if app_config.clipboard != self.last_clipboard1:
                    self.last_clipboard1 = app_config.clipboard
                    pyperclip.copy(self.last_clipboard1)

            except Exception as e:
                print(f"[Clipboard] Error: {e}")
            time.sleep(0.5)

    def clipboard_sender(self,_socket):
        try:
            data = {"type": "clipboard", "content": app_config.clipboard}
            _socket.sendall((json.dumps(data) + "\n").encode())
        except Exception as e:
            print(f"[Clipboard] Error: {e}")
            logging.info(f"[Clipboard] Error: {e}")

    def handle_primary(self, client_socket):
        threading.Thread(target=self.monitor_mouse_edges,args=(client_socket,), daemon=True).start()
        threading.Thread(target=self.input_sender_mouse, args=(client_socket,), daemon=True).start()

    def handle_secondary(self, sec_socket):        
        threading.Thread(target=self.input_sender_keyboard, args=(sec_socket,), daemon=True).start()

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.primary_port))
        self.server_socket.listen(1)
        print("[Server] Waiting for Client to connect")
        logging.info("[Server] Waiting for Client to connect")

        def accept_primary():
            client, addr = self.server_socket.accept()
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"[Server] Primary connection from: {addr}")
            client.sendall(b'CONNECTED\n')
            self.handle_primary(client)

        def accept_secondary():
            def read_clipboard():
                while app_config.is_running:
                    try:
                        data = self.secondary_server.recv(1024).decode()
                        if not data:
                            break
                        else:
                            try:
                                evt = json.loads(data)
                                if evt["type"] == "clipboard":
                                    current_clipboard = evt["content"]
                                    if current_clipboard != pyperclip.paste():
                                        app_config.clipboard = current_clipboard
                                        pyperclip.copy(evt["content"])
                                        app_config.save()
                                        logging.info("[Clipboard] Updated.")
                            except json.JSONDecodeError as e:
                                print(f"[Clipboard] JSON decode error: {e}")
                    except Exception as e:
                        print(f"[Clipboard] Error reading clipboard data: {e}")
            sec_socket, sec_addr = self.secondary_server_socket.accept()
            sec_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"[Server] Secondary connection from: {sec_addr}")
            self.secondary_server = sec_socket
            self.handle_secondary(sec_socket)
            threading.Thread(target=read_clipboard, daemon=True).start()
            logging.info("[Server] Connected Successfully")

        self.secondary_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.secondary_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.secondary_server_socket.bind(("0.0.0.0", self.secondary_port))
        self.secondary_server_socket.listen(1)
        
        threading.Thread(target=accept_primary, daemon=True).start()
        threading.Thread(target=accept_secondary, daemon=True).start()

    def start_client(self):

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        self.secondary_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.secondary_client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            import win32api 
        except:
            print("")
        print(f"[Client] Connecting to {app_config.server_ip}:{self.primary_port}")
        c1,c2 = 5,5
        for i in range(c1,0,-1):
            try:
                self.client_socket.connect((app_config.server_ip, self.primary_port))
                if self.client_socket.recv(1024) != b'CONNECTED\n':
                    raise Exception("Handshake failed")
                break
            except Exception as e:
                print(f"Retrying connection Attempt: {i}")
                logging.info(f"Retrying connection Attempt: {i}")
                time.sleep(1)
                if i == 0:
                    print(f"[Client] Connection failed: {e}")
                    logging.info(f"[Client] Connection failed: {e}")
                    app_config.is_running = False
                    self.cleanup()
                    app_config.save()
                    return
        print("[Client] Primary Connected")

        def receive_primary():
            buffer = ""
            while app_config.is_running:
                try:
                    data = self.client_socket.recv(1024).decode()
                except Exception as e:
                    print(f"[Client] Receive error: {e}")
                    app_config.is_running = False
                    app_config.save()
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
                            if self.os_type == "linux":
                                self.mouse_controller.position = (x, y)
                            elif self.os_type == "windows":
                                win32api.SetCursorPos((x, y))
                        elif evt["type"] == "click":
                            btn = getattr(Button, evt['button'])
                            if evt['pressed']:
                                self.mouse_controller.press(btn)
                            else:
                                self.mouse_controller.release(btn)
                        elif evt["type"] == "scroll":
                            self.mouse_controller.scroll(evt['dx'], evt['dy'])
                    except Exception as e:
                        print(f"[Client] Parse error: {e}")

        print(f"[Client] Connecting to {app_config.server_ip}:{self.secondary_port}")
        for i in range(c2,0,-1):
            try:
                self.secondary_client_socket.connect((app_config.server_ip, self.secondary_port))
                logging.info("[Client] Connected successfully.")
                print("[Client] Connected successfully.")
                break
            except Exception as e:
                logging.info(f"Retrying connection Attemp: {i}")
                print(f"Retrying connection Attemp: {i}")
                time.sleep(1)
                if i == 0:
                    print(f"[Client] Connection failed: {e}")
                    logging.info(f"[Client] Connection failed: {e}")
                    app_config.is_running = False
                    self.cleanup()
                    app_config.save()
                    return 
        print("[Client] Secondary Connected")
                
        def receive_secondary():
            def parse_key(key_str):
                if key_str.startswith("Key."):
                    try:
                        return getattr(Key, key_str.split(".", 1)[1])
                    except AttributeError:
                        print(f"[Parse] Unknown special key: {key_str}")
                        return None
                return key_str
            buffer = ""
            while app_config.is_running:
                try:
                    data = self.secondary_client_socket.recv(1024).decode()
                except Exception as e:
                    print(f"[Client] Secondary receive error: {e}")
                    app_config.is_running = False
                    app_config.save()
                    break
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    try:
                        evt = json.loads(line)
                        if evt["type"] == "key_press":
                            key = parse_key(evt["key"])
                            if key:
                                self.keyboard_controller.press(key)
                        elif evt["type"] == "key_release":
                            key = parse_key(evt["key"])
                            if key:
                                self.keyboard_controller.release(key)
                        elif evt["type"] == "active_device":
                            app_config.active_device = evt["value"]
                            app_config.save()
                            if not app_config.active_device:
                                if self.last_send != pyperclip.paste():
                                    self.last_send = pyperclip.paste()
                                    self.clipboard_sender(self.secondary_client_socket)
                                    print('[Clipboard] send to server')
                        elif evt["type"] == "clipboard":
                            if pyperclip.paste() != evt["content"]:
                                app_config.clipboard = evt["content"]
                                pyperclip.copy(evt["content"])
                                app_config.save()
                                print("[Clipboard] Updated clipboard content")
                                logging.info("[Clipboard] Updated.")
                    except Exception as e:
                        print(f"[Client] Secondary parse error: {e}")

        threading.Thread(target=receive_primary, daemon=True).start()
        threading.Thread(target=receive_secondary, daemon=True).start()

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
        threading.Thread(target=self.clipboard_monitor,daemon=True).start()
        threading.Thread(target=monitor_stop, daemon=True).start()

        if self.os_type == "windows":
            self.gui_app.mainloop()
        else:
            self.gui_app.exec_()

if __name__ == "__main__":
    MouseSyncApp().run()
