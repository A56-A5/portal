# invis.py
import sys
import socket
import threading
import json
import time
import platform
from pynput import mouse
from pynput.mouse import Button, Controller
from config import app_config

OS = platform.system().lower()

class MouseSyncApp:
    def __init__(self):
        self.edge_transition_cooldown = False
        self.port = 50007
        self.mouse_controller = Controller()
        self.server_socket = None
        self.client_socket = None
        self.overlay = None
        self.screen_width = None
        self.screen_height = None
        self.gui_app = None
        self.client_thread = None
        self.listener_thread = None
        self.os_type = OS

        app_config.load()
        app_config.active_device = False

        if OS == "windows":
            import tkinter as tk
            self.tk = tk
            self.gui_app = self.tk.Tk()
            self.gui_app.withdraw()
            self.screen_width = self.gui_app.winfo_screenwidth()
            self.screen_height = self.gui_app.winfo_screenheight()
        elif OS == "linux":
            from PyQt5.QtWidgets import QApplication, QWidget
            from PyQt5.QtCore import Qt,QTimer
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
                self.client_socket = None
                print("[Client] Socket closed.")
        except Exception as e:
            print(f"[Client] Error closing socket: {e}")

        try:
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
                print("[Server] Socket closed.")
        except Exception as e:
            print(f"[Server] Error closing socket: {e}")

        if self.overlay:
            self.destroy_overlay()

    def create_overlay(self):
        if not app_config.active_device:
            return
        if OS == "windows":
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
        elif OS == "linux":
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
            if OS == "windows":
                self.overlay.destroy()
            elif OS == "linux":
                self.overlay.close()
            self.overlay = None

    def handle_client(self, client_socket):
        last_sent_time = [0]  # Mutable for inner access
        min_send_interval = 1 / 30  # 60 FPS cap (adjust as needed)
        def on_move(x, y):
            margin = 2
            server_mouse_controller = Controller()
            # Entry
            from PyQt5.QtCore import QTimer
            if not app_config.active_device and not self.edge_transition_cooldown:
                if app_config.server_direction == "Right" and x >= self.screen_width - margin:
                    app_config.active_device = True
                    self.edge_transition_cooldown = True
                    if self.os_type == "windows":
                        self.gui_app.after(0,self.create_overlay())
                        self.gui_app.after(10, lambda: setattr(server_mouse_controller, 'position', (margin, y)))
                    elif self.os_type == "linux":
                        self.create_overlay()
                        server_mouse_controller.position = (margin, y)
                    print("Mouse Exited from Right edge")
                elif app_config.server_direction == "Left" and x <= margin:
                    app_config.active_device = True
                    self.edge_transition_cooldown = True
                    if self.os_type == "windows":
                        self.gui_app.after(0, self.create_overlay)
                        self.gui_app.after(10, lambda: setattr(server_mouse_controller, 'position', (self.screen_width - margin, y)))
                    elif self.os_type == "linux":
                        self.create_overlay()
                        server_mouse_controller.position = (self.screen_width - margin, y)
                    print("Mouse Exited from Left edge")
                elif app_config.server_direction == "Top" and y <= margin:
                    app_config.active_device = True
                    self.edge_transition_cooldown = True
                    if self.os_type == "windows":
                        self.gui_app.after(0, self.create_overlay)
                        self.gui_app.after(10, lambda: setattr(server_mouse_controller, 'position', (x, self.screen_height - margin)))
                    elif self.os_type == "linux":
                        self.create_overlay()
                        server_mouse_controller.position = (x, self.screen_height - margin)
                    print("Mouse Exited from Top edge")
                elif app_config.server_direction == "Bottom" and y >= self.screen_height - margin:
                    app_config.active_device = True
                    self.edge_transition_cooldown = True
                    if self.os_type == "windows":
                        self.gui_app.after(0, self.create_overlay)
                        self.gui_app.after(10, lambda: setattr(server_mouse_controller, 'position', (x, margin)))
                    elif self.os_type == "linux":
                        self.create_overlay()
                        server_mouse_controller.position = (x, margin)
                    print("Mouse Exited from Bottom edge")
        
            # Return
            elif app_config.active_device and not self.edge_transition_cooldown:
                if app_config.server_direction == "Right" and x <= margin:
                    app_config.active_device = False
                    self.edge_transition_cooldown = True
                    if self.os_type == "windows":
                        self.gui_app.after(0, self.destroy_overlay)
                        self.gui_app.after(10, lambda: setattr(server_mouse_controller, 'position', (self.screen_width - margin, y)))
                    elif self.os_type == "linux":
                        self.destroy_overlay()
                        server_mouse_controller.position = (self.screen_width - margin, y)
                    print("Mouse Entered from Right edge")
                elif app_config.server_direction == "Left" and x >= self.screen_width - margin:
                    app_config.active_device = False
                    self.edge_transition_cooldown = True
                    if self.os_type == "windows":
                        self.gui_app.after(0, self.destroy_overlay)
                        self.gui_app.after(10, lambda: setattr(server_mouse_controller, 'position', (margin, y)))
                    elif self.os_type == "linux":
                        self.destroy_overlay()
                        server_mouse_controller.position = (margin, y)
                    print("Mouse Entered from Left edge")
                elif app_config.server_direction == "Top" and y >= self.screen_height - margin:
                    app_config.active_device = False
                    self.edge_transition_cooldown = True
                    if self.os_type == "windows":
                        self.gui_app.after(0, self.destroy_overlay)
                        self.gui_app.after(10, lambda: setattr(server_mouse_controller, 'position', (x, margin)))
                    elif self.os_type == "linux":
                        self.destroy_overlay()
                        server_mouse_controller.position = (x, margin)
                    print("Mouse Entered from Top edge")
                elif app_config.server_direction == "Bottom" and y <= margin:
                    app_config.active_device = False
                    self.edge_transition_cooldown = True
                    if self.os_type == "windows":
                        self.gui_app.after(0, self.destroy_overlay)
                        self.gui_app.after(10, lambda: setattr(server_mouse_controller, 'position', (x, self.screen_height - margin)))
                    elif self.os_type == "linux":
                        self.destroy_overlay()
                        server_mouse_controller.position = (x, self.screen_height - margin)
                    print("Mouse Entered from Bottom edge")
        
            # Reset cooldown if mouse is not at any edge
            if (
                margin < x < self.screen_width - margin and
                margin < y < self.screen_height - margin
            ):
                self.edge_transition_cooldown = False
        
            # Send movement
            if not app_config.active_device:
                return
            
            if self.os_type == "linux":
                now = time.time()
            if now - last_sent_time[0] < min_send_interval:
                return
            last_sent_time[0] = now
        
            try:
                norm_x = x / self.screen_width
                norm_y = y / self.screen_height
                data = json.dumps({"type": "move", "x": norm_x, "y": norm_y}) + "\n"
                client_socket.sendall(data.encode())
            except Exception as e:
                print(f"[Server] Send failed: {e}")
                return False
        

        def on_click(x, y, button, pressed):
            if not app_config.active_device:
                return
            try:
                data = json.dumps({"type": "click", "button": button.name, "pressed": pressed}) + "\n"
                client_socket.sendall(data.encode())
            except:
                return False

        def on_scroll(x, y, dx, dy):
            if not app_config.active_device:
                return
            try:
                data = json.dumps({"type": "scroll", "dx": dx, "dy": dy}) + "\n"
                client_socket.sendall(data.encode())
            except:
                return False

        def listener_thread():
            with mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll) as listener:
                listener.join()

        threading.Thread(target=listener_thread, daemon=True).start()

    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.port))
        self.server_socket.listen(1)
        print(f"[Server] Listening on port {self.port}")

        def server_thread():
            try:
                print("[Server] Waiting for client...")
                client, addr = self.server_socket.accept()
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                print(f"[Server] Client connected: {addr}")
                client.sendall(b'CONNECTED\n')
                self.handle_client(client)
            except Exception as e:
                print(f"[Server] Error: {e}")

        threading.Thread(target=server_thread, daemon=True).start()

    def start_client(self):
        print("[Client] Trying to connect to", app_config.server_ip)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            self.client_socket.connect((app_config.server_ip, self.port))
            if self.client_socket.recv(1024) != b"CONNECTED\n":
                raise Exception("Handshake failed")
            print(f"[Client] Connected to server {app_config.server_ip}:{self.port}")
            if self.os_type == "windows":
                import win32api
            def client_thread():
                buffer = ""
                last_move_time = 0
                move_interval = 1 / 30

                try:
                    while app_config.is_running:
                        data = self.client_socket.recv(1024).decode()
                        if not data:
                            break
                        buffer += data
                        latest_move_event = None
                        events_to_process = []
                        
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            event = json.loads(line)
                            if event["type"] == "move":
                                latest_move_event = event  # Only keep the latest move
                            else:
                                events_to_process.append(event)
                        
                        # Process only the latest move
                        if latest_move_event:
                            now = time.time()
                            if self.os_type == "linux":
                                self.mouse_controller.position = (
                                    int(latest_move_event["x"] * self.screen_width),
                                    int(latest_move_event["y"] * self.screen_height)
                                )
                            elif self.os_type == "windows" and now - last_move_time >= move_interval:
                                last_move_time = now
                                self.mouse_controller.position = (
                                    int(latest_move_event["x"] * self.screen_width),
                                    int(latest_move_event["y"] * self.screen_height)
                                )
                        
                        # Process other events normally
                        for event in events_to_process:
                            if event["type"] == "click":
                                btn = getattr(Button, event['button'])
                                if event['pressed']:
                                    self.mouse_controller.press(btn)
                                else:
                                    self.mouse_controller.release(btn)
                            elif event["type"] == "scroll":
                                self.mouse_controller.scroll(event['dx'], event['dy'])
                except ConnectionResetError:
                    print("[Client] Server forcibly closed connection.")
                except Exception as e:
                    print(f"[Client] Unexpected error: {e}")

            threading.Thread(target=client_thread, daemon=True).start()
        except Exception as e:
            print(f"[Client] Connection failed: {e}")

    def run(self):
        app_config.is_running = True
        if app_config.mode == "server":
            self.start_server()
        else:
            self.start_client()

        def stop_check_loop():
            while app_config.is_running and not app_config.stop_flag:
                time.sleep(0.5)
            print("[System] Stopping invis.py due to stop_flag.")
            self.cleanup()
            self.gui_app.quit()

        threading.Thread(target=stop_check_loop, daemon=True).start()

        if OS == "windows":
            self.gui_app.mainloop()
        else:
            self.gui_app.exec_()

if __name__ == "__main__":
    MouseSyncApp().run()
