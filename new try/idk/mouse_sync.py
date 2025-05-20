import sys
import socket
import threading
import json
from pynput import mouse
from pynput.mouse import Controller
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QLineEdit, QRadioButton, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer

class MouseSyncApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mouse Sync")
        self.setGeometry(100, 100, 300, 400)

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
        layout = QVBoxLayout()

        mode_group = QGroupBox("Mode")
        mode_layout = QHBoxLayout()
        self.server_radio = QRadioButton("Server")
        self.client_radio = QRadioButton("Client")
        self.server_radio.setChecked(True)
        self.server_radio.toggled.connect(self.update_mode)
        self.client_radio.toggled.connect(self.update_mode)
        mode_layout.addWidget(self.server_radio)
        mode_layout.addWidget(self.client_radio)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        self.ip_input = QLineEdit(self.server_ip)
        layout.addWidget(QLabel("Server IP"))
        layout.addWidget(self.ip_input)

        layout.addWidget(QLabel(f"Screen: {self.screen_width}x{self.screen_height}"))

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.toggle_connection)
        layout.addWidget(self.start_button)

        self.status_label = QLabel("Status: Disconnected")
        layout.addWidget(self.status_label)

        self.setLayout(layout)
        self.update_mode()

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
            print(f"[Error] Connection failed: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to start: {str(e)}")

    def stop_connection(self):
        print("[System] Stopping connection...")
        self.is_running = False

        if self.overlay:
            self.overlay.close()
            self.overlay = None

        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None

        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None

        self.start_button.setText("Start")
        self.status_label.setText("Status: Disconnected")
        print("[System] Connection stopped")

    def create_overlay(self):
        print("[Overlay] Creating full-screen transparent overlay")
        self.overlay = QWidget()
        self.overlay.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.overlay.setAttribute(Qt.WA_TranslucentBackground)
        self.overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
        self.overlay.setCursor(Qt.BlankCursor)
        self.overlay.show()

    def handle_client(self, client_socket):
        print("[Server] Starting absolute normalized mouse position tracking...")
        QTimer.singleShot(0, self.create_overlay)

        def on_move(x, y):
            if not self.is_running:
                return False
            try:
                normalized_x = x / self.screen_width
                normalized_y = y / self.screen_height
                data = json.dumps({"x": normalized_x, "y": normalized_y}) + '\n'
                client_socket.sendall(data.encode())
            except Exception as e:
                print(f"[Server] Send error: {e}")
                self.stop_connection()
                return False

        def listener_thread():
            print("[Server] Mouse listener thread started")
            with mouse.Listener(on_move=on_move) as listener:
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
                print(f"[Server] Client connected: {addr}")
                client.sendall(b'CONNECTED\n')
                self.handle_client(client)
            except Exception as e:
                if self.is_running:
                    print(f"[Server] Error: {e}")
                self.stop_connection()

        threading.Thread(target=server_thread, daemon=True).start()

    def start_client(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.ip_input.text(), self.port))
        print(f"[Client] Connected to server {self.ip_input.text()}:{self.port}")

        data = self.client_socket.recv(1024)
        if data != b'CONNECTED\n':
            raise Exception("Failed handshake with server")

        client_screen_width = QApplication.primaryScreen().size().width()
        client_screen_height = QApplication.primaryScreen().size().height()
        print(f"[Client] Screen dimensions: {client_screen_width}x{client_screen_height}")

        def client_thread():
            print("[Client] Receiving mouse positions...")
            buffer = ""
            while self.is_running:
                try:
                    data = self.client_socket.recv(1024).decode()
                    if not data:
                        print("[Client] Server closed connection")
                        break
                    buffer += data
                    while '\n' in buffer:
                        msg, buffer = buffer.split('\n', 1)
                        try:
                            pos = json.loads(msg)
                            abs_x = int(pos['x'] * client_screen_width)
                            abs_y = int(pos['y'] * client_screen_height)
                            self.mouse_controller.position = (abs_x, abs_y)
                        except Exception as e:
                            print(f"[Client] Error parsing position: {e}")
                except Exception as e:
                    if self.is_running:
                        print(f"[Client] Error: {e}")
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
