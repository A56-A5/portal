import sys
import socket
import threading
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QRadioButton, QLabel, QPushButton, QLineEdit, QGroupBox, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import Qt
from pynput import mouse
from pynput.mouse import Controller


class MouseSyncApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mouse Sync")
        self.setGeometry(100, 100, 300, 400)

        self.screen_width = QApplication.desktop().screenGeometry().width()
        self.screen_height = QApplication.desktop().screenGeometry().height()
        print(f"[System] Screen dimensions: {self.screen_width}x{self.screen_height}")

        self.is_server = True
        self.server_ip = "127.0.0.1"
        self.port = 50007
        self.is_running = False
        self.server_socket = None
        self.client_socket = None
        self.mouse_controller = Controller()

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        layout = QVBoxLayout()

        # Mode selector
        mode_box = QGroupBox("Mode")
        mode_layout = QHBoxLayout()
        self.server_radio = QRadioButton("Server")
        self.server_radio.setChecked(True)
        self.client_radio = QRadioButton("Client")
        self.server_radio.toggled.connect(self.update_mode)
        mode_layout.addWidget(self.server_radio)
        mode_layout.addWidget(self.client_radio)
        mode_box.setLayout(mode_layout)

        # Server IP
        ip_box = QGroupBox("Server IP")
        ip_layout = QVBoxLayout()
        self.ip_entry = QLineEdit(self.server_ip)
        ip_layout.addWidget(self.ip_entry)
        ip_box.setLayout(ip_layout)

        # Screen info
        screen_box = QGroupBox("Screen Info")
        screen_layout = QVBoxLayout()
        self.screen_label = QLabel(f"Screen: {self.screen_width}x{self.screen_height}")
        screen_layout.addWidget(self.screen_label)
        screen_box.setLayout(screen_layout)

        # Buttons and status
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.toggle_connection)
        self.status_label = QLabel("Status: Disconnected")

        layout.addWidget(mode_box)
        layout.addWidget(ip_box)
        layout.addWidget(screen_box)
        layout.addWidget(self.start_button)
        layout.addWidget(self.status_label)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        self.update_mode()

    def update_mode(self):
        self.is_server = self.server_radio.isChecked()
        self.ip_entry.setDisabled(self.is_server)
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
        print("[System] Connection stopped")

    def handle_client(self, client_socket):
        print("[Server] Starting absolute normalized mouse position tracking...")

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
        self.client_socket.connect((self.ip_entry.text(), self.port))
        print(f"[Client] Connected to server {self.ip_entry.text()}:{self.port}")

        data = self.client_socket.recv(1024)
        if data != b'CONNECTED\n':
            raise Exception("Failed handshake with server")

        client_screen_width = QApplication.desktop().screenGeometry().width()
        client_screen_height = QApplication.desktop().screenGeometry().height()
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
