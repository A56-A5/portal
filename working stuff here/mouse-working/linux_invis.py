import sys
import socket
import threading
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QLineEdit, QRadioButton, QButtonGroup, QFrame
)
from PyQt5.QtCore import Qt, QTimer
from pynput import mouse 
from pynput.mouse import Button
from pynput.mouse import Controller

class MouseSyncApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Mouse Sync")
        self.setFixedSize(300, 400)

        self.screen_width = QApplication.primaryScreen().size().width()
        self.screen_height = QApplication.primaryScreen().size().height()
        print(f"[System] Screen dimensions: {self.screen_width}x{self.screen_height}")

        self.is_server = True
        self.server_ip = "127.0.0.1"
        self.port = 50007
        self.is_running = False
        self.server_socket = None
        self.client_socket = None
        self.mouse_controller = Controller()
        self.overlay = None

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        mode_frame = QFrame()
        mode_layout = QHBoxLayout()
        self.server_radio = QRadioButton("Server")
        self.server_radio.setChecked(True)
        self.client_radio = QRadioButton("Client")

        mode_group = QButtonGroup()
        mode_group.addButton(self.server_radio)
        mode_group.addButton(self.client_radio)
        self.server_radio.toggled.connect(self.update_mode)

        mode_layout.addWidget(self.server_radio)
        mode_layout.addWidget(self.client_radio)
        mode_frame.setLayout(mode_layout)
        layout.addWidget(QLabel("Mode:"))
        layout.addWidget(mode_frame)

        layout.addWidget(QLabel("Server IP:"))
        self.ip_input = QLineEdit(self.server_ip)
        self.ip_input.setEnabled(False)
        layout.addWidget(self.ip_input)

        layout.addWidget(QLabel(f"Screen: {self.screen_width}x{self.screen_height}"))

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.toggle_connection)
        layout.addWidget(self.start_button)

        self.status_label = QLabel("Status: Disconnected")
        layout.addWidget(self.status_label)

    def update_mode(self):
        self.is_server = self.server_radio.isChecked()
        self.ip_input.setEnabled(not self.is_server)
        print(f"[Mode] Switched to {'Server' if self.is_server else 'Client'} mode")

    def toggle_connection(self):
        if not self.is_running:
            self.start_connection()
        else:
            self.stop_connection()

    def start_connection(self):
        try:
            if self.is_server:
                self.start_server()
            else:
                self.start_client()
            self.is_running = True
            self.start_button.setText("Stop")
            self.status_label.setText("Status: Connected")
        except Exception as e:
            print(f"[Error] Connection failed: {e}")
            self.status_label.setText("Status: Error")
            self.stop_connection()

    def stop_connection(self):
        print("[System] Stopping connection...")
        self.is_running = False

        if self.overlay:
            self.overlay.close()
            self.overlay = None

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None

        self.start_button.setText("Start")
        self.status_label.setText("Status: Disconnected")

    def create_overlay(self):
        print("[Overlay] Creating full-screen transparent overlay")
        self.overlay = QWidget()
        self.overlay.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.overlay.setAttribute(Qt.WA_TranslucentBackground)
        self.overlay.setCursor(Qt.BlankCursor)
        self.overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        self.overlay.setWindowOpacity(0.0)
        self.overlay.show()
        self.overlay.raise_()
        print("[Overlay] Overlay is now active and covering full screen")

    def handle_client(self, client_socket):
        print("[Server] Starting mouse tracking...")
        QTimer.singleShot(0, self.create_overlay)

        def on_move(x, y):
            if not self.is_running:
                return False
            try:
                norm_x = x / self.screen_width
                norm_y = y / self.screen_height
                payload = json.dumps({"type": "move", "x": norm_x, "y": norm_y}) + "\n"
                client_socket.sendall(payload.encode())
            except Exception as e:
                print(f"[Server] Send error: {e}")
                self.stop_connection()
                return False

        def on_click(x, y, button, pressed):
            if not self.is_running:
                return False
            try:
                data = json.dumps({"type": "click", "button": button.name, "pressed": pressed}) + "\n"
                client_socket.sendall(data.encode())
            except Exception as e:
                print(f"[Server] Click send error: {e}")
                self.stop_connection()
                return False

        def on_scroll(x, y, dx, dy):
            if not self.is_running:
                return False
            try:
                data = json.dumps({"type": "scroll", "dx": dx, "dy": dy}) + "\n"
                client_socket.sendall(data.encode())
            except Exception as e:
                print(f"[Server] Scroll send error: {e}")
                self.stop_connection()
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

        def accept_thread():
            try:
                client, addr = self.server_socket.accept()
                print(f"[Server] Client connected from {addr}")
                client.sendall(b"CONNECTED\n")
                self.handle_client(client)
            except Exception as e:
                print(f"[Server] Error: {e}")
                self.stop_connection()

        threading.Thread(target=accept_thread, daemon=True).start()

    def start_client(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.ip_input.text(), self.port))
        print(f"[Client] Connected to server {self.ip_input.text()}:{self.port}")

        if self.client_socket.recv(1024) != b"CONNECTED\n":
            raise Exception("Handshake failed")

        def client_thread():
            print("[Client] Receiving mouse events...")
            buffer = ""
            while self.is_running:
                try:
                    data = self.client_socket.recv(1024).decode()
                    if not data:
                        print("[Client] Server closed connection")
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
                        except Exception as e:
                            print(f"[Client] Parse error: {e} → data: {line}")
                except Exception as e:
                    if self.is_running:
                        print(f"[Client] Connection error: {e}")
                    break

        threading.Thread(target=client_thread, daemon=True).start()

    def closeEvent(self, event):
        self.stop_connection()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MouseSyncApp()
    window.show()
    sys.exit(app.exec_())
