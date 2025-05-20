import sys
import socket
import threading
import json
from PyQt5.QtWidgets import QApplication, QWidget, QLabel
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QCursor
from pynput import mouse
from pynput.mouse import Controller


PORT = 50007


class ServerThread(QThread):
    error = pyqtSignal(str)
    connected = pyqtSignal(object)

    def run(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("0.0.0.0", PORT))
            server_socket.listen(1)
            print("[Server] Listening for connection...")
            client, addr = server_socket.accept()
            print(f"[Server] Client connected: {addr}")
            client.sendall(b'CONNECTED\n')
            self.connected.emit(client)
        except Exception as e:
            self.error.emit(str(e))


class TransparentMouseSync(QWidget):
    def __init__(self, is_server=True, server_ip="127.0.0.1"):
        super().__init__()

        self.is_server = is_server
        self.server_ip = server_ip
        self.client_socket = None
        self.server_socket = None
        self.mouse_controller = Controller()
        self.running = True

        # Transparent fullscreen overlay
        self.setWindowOpacity(0.0)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.showFullScreen()
        self.setCursor(Qt.BlankCursor)

        if is_server:
            self.start_server()
        else:
            self.start_client()

    def start_server(self):
        self.server_thread = ServerThread()
        self.server_thread.connected.connect(self.handle_client)
        self.server_thread.error.connect(self.display_error)
        self.server_thread.start()

    def handle_client(self, client_socket):
        print("[Server] Starting to send normalized mouse position")
        self.client_socket = client_socket

        def on_move(x, y):
            if not self.running:
                return False
            try:
                screen_w = self.screen().size().width()
                screen_h = self.screen().size().height()
                normalized_x = x / screen_w
                normalized_y = y / screen_h
                data = json.dumps({"x": normalized_x, "y": normalized_y}) + '\n'
                client_socket.sendall(data.encode())
            except Exception as e:
                print(f"[Server] Send error: {e}")
                self.running = False
                return False

        threading.Thread(target=lambda: mouse.Listener(on_move=on_move).run(), daemon=True).start()

    def start_client(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_ip, PORT))
            data = self.client_socket.recv(1024)
            if data != b'CONNECTED\n':
                raise Exception("Failed handshake")
            print("[Client] Connected and ready to receive")

            threading.Thread(target=self.client_listener, daemon=True).start()
        except Exception as e:
            self.display_error(str(e))

    def client_listener(self):
        screen_w = self.screen().size().width()
        screen_h = self.screen().size().height()
        buffer = ""
        while self.running:
            try:
                data = self.client_socket.recv(1024).decode()
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    msg, buffer = buffer.split('\n', 1)
                    pos = json.loads(msg)
                    abs_x = int(pos['x'] * screen_w)
                    abs_y = int(pos['y'] * screen_h)
                    self.mouse_controller.position = (abs_x, abs_y)
            except Exception as e:
                print(f"[Client] Error: {e}")
                break

    def display_error(self, message):
        print(f"[Error] {message}")
        self.running = False
        self.close()

    def closeEvent(self, event):
        self.running = False
        try:
            if self.client_socket:
                self.client_socket.close()
        except:
            pass
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Change is_server and server_ip here
    tracker = TransparentMouseSync(is_server=True, server_ip="127.0.0.1")
    sys.exit(app.exec_())
