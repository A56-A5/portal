import sys
import socket
import threading
import json
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCursor
from pynput import mouse
from pynput.mouse import Controller

PORT = 50007


class ServerThread(QThread):
    connected = pyqtSignal(object)
    error = pyqtSignal(str)

    def run(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(("0.0.0.0", PORT))
            server_socket.listen(1)
            print("[Server] Listening for connection...")
            client, addr = server_socket.accept()
            print(f"[Server] Client connected from {addr}")
            client.sendall(b"CONNECTED\n")
            self.connected.emit(client)
        except Exception as e:
            self.error.emit(str(e))


class TransparentMouseSync(QWidget):
    def __init__(self, is_server=True, server_ip="127.0.0.1"):
        super().__init__()

        self.is_server = is_server
        self.server_ip = server_ip
        self.client_socket = None
        self.running = True
        self.mouse_controller = Controller()

        # Fullscreen, transparent, no cursor
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.0)
        self.setCursor(Qt.BlankCursor)
        self.showFullScreen()

        if is_server:
            self.start_server()
        else:
            self.start_client()

    def start_server(self):
        self.server_thread = ServerThread()
        self.server_thread.connected.connect(self.start_mouse_tracking)
        self.server_thread.error.connect(self.handle_error)
        self.server_thread.start()

    def start_mouse_tracking(self, client_socket):
        self.client_socket = client_socket

        def on_move(x, y):
            try:
                screen_w = self.screen().size().width()
                screen_h = self.screen().size().height()
                norm_x = x / screen_w
                norm_y = y / screen_h
                payload = json.dumps({"x": norm_x, "y": norm_y}) + "\n"
                self.client_socket.sendall(payload.encode())
            except Exception as e:
                print(f"[Server] Error sending data: {e}")
                return False

        threading.Thread(target=lambda: mouse.Listener(on_move=on_move).run(), daemon=True).start()

    def start_client(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.server_ip, PORT))
            if sock.recv(1024) != b"CONNECTED\n":
                raise Exception("Handshake failed")
            self.client_socket = sock
            threading.Thread(target=self.receive_mouse_data, daemon=True).start()
        except Exception as e:
            self.handle_error(str(e))

    def receive_mouse_data(self):
        screen_w = self.screen().size().width()
        screen_h = self.screen().size().height()
        buffer = ""
        while self.running:
            try:
                data = self.client_socket.recv(1024).decode()
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    try:
                        coords = json.loads(line)
                        x = int(coords["x"] * screen_w)
                        y = int(coords["y"] * screen_h)
                        self.mouse_controller.position = (x, y)
                    except Exception as e:
                        print(f"[Client] Parse error: {e} → data: {line}")
            except Exception as e:
                print(f"[Client] Connection error: {e}")
                break

    def handle_error(self, msg):
        print(f"[Error] {msg}")
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
    # Change `is_server` and `server_ip` to switch roles
    tracker = TransparentMouseSync(is_server=True, server_ip="127.0.0.1")
    sys.exit(app.exec_())
