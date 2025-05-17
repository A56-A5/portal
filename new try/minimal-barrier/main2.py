import sys
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QGroupBox, QRadioButton,
    QPushButton, QLineEdit, QLabel, QCheckBox, QHBoxLayout, QMessageBox, QComboBox
)
from PyQt5.QtCore import Qt
from audio_share import AudioShareWidget, start_audio_share, stop_audio_share
import threading
import socket
import time
from pynput.mouse import Controller as MouseController, Listener as MouseListener
from pynput.mouse import Button
import platform
import json
import os

# Placeholders for mouse, keyboard, clipboard sharing logic
# (to be implemented in next steps)
def start_mouse_share_server():
    pass
def start_mouse_share_client(ip):
    pass
def start_keyboard_share_server():
    pass
def start_keyboard_share_client(ip):
    pass
def start_clipboard_share_server():
    pass
def start_clipboard_share_client(ip):
    pass

def stop_all_sharing():
    pass

MOUSE_PORT = 50010

# Helper to get screen size cross-platform
try:
    import pyautogui
    def get_screen_size():
        return pyautogui.size()
except ImportError:
    pass

if 'get_screen_size' not in globals():
    def get_screen_size():
        if platform.system() == 'Windows':
            from ctypes import windll
            return windll.user32.GetSystemMetrics(0), windll.user32.GetSystemMetrics(1)
        else:
            return 1920, 1080  # fallback

# Mouse sharing logic
mouse_sharing_thread = None
mouse_sharing_running = False

OPPOSITE_EDGE = {
    'Left': 'Right',
    'Right': 'Left',
    'Top': 'Bottom',
    'Bottom': 'Top'
}

# Edge mapping for pointer entry on client
ENTRY_EDGE_TO_CLIENT_POS = {
    'Left': lambda w, h: (1, h // 2),         # Enter from server's right, appear at left
    'Right': lambda w, h: (w - 2, h // 2),   # Enter from server's left, appear at right
    'Top': lambda w, h: (w // 2, 1),         # Enter from server's bottom, appear at top
    'Bottom': lambda w, h: (w // 2, h - 2),  # Enter from server's top, appear at bottom
}

# Helper functions to hide/show mouse pointer (Windows/Linux, robust)
def hide_cursor():
    if platform.system() == 'Windows':
        import ctypes
        ctypes.windll.user32.ShowCursor(False)
    elif platform.system() == 'Linux':
        try:
            from Xlib import display, X
            dsp = display.Display()
            root = dsp.screen().root
            invisible_cursor = dsp.screen().root.create_pixmap(1, 1, 1)
            color = dsp.screen().default_colormap.alloc_color(0, 0, 0)
            cursor = root.create_cursor(invisible_cursor, invisible_cursor, color.pixel, color.pixel, 0, 0)
            root.change_attributes(cursor=cursor)
            dsp.sync()
        except Exception:
            os.system('xsetroot -cursor_name none')
def show_cursor():
    if platform.system() == 'Windows':
        import ctypes
        ctypes.windll.user32.ShowCursor(True)
    elif platform.system() == 'Linux':
        try:
            from Xlib import display, X
            dsp = display.Display()
            root = dsp.screen().root
            root.change_attributes(cursor=X.NONE)
            dsp.sync()
        except Exception:
            os.system('xsetroot -cursor_name left_ptr')

def start_mouse_share_server(edge):
    global mouse_sharing_thread, mouse_sharing_running
    mouse_sharing_running = True
    def server_thread():
        mouse = MouseController()
        width, height = get_screen_size()
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', MOUSE_PORT))
        s.listen(1)
        print("[Mouse] Waiting for client connection...")
        try:
            conn, addr = s.accept()
            print(f"[Mouse] Client connected: {addr}")
            pointer_on_server = True
            pointer_on_client = False
            def on_move(x, y):
                nonlocal pointer_on_server, pointer_on_client
                if not pointer_on_server:
                    return True
                hit_edge = False
                if edge == 'Left' and x <= 0:
                    hit_edge = True
                elif edge == 'Right' and x >= width - 1:
                    hit_edge = True
                elif edge == 'Top' and y <= 0:
                    hit_edge = True
                elif edge == 'Bottom' and y >= height - 1:
                    hit_edge = True
                if hit_edge:
                    pointer_on_server = False
                    pointer_on_client = True
                    hide_cursor()
                    try:
                        conn.sendall(f'ENTER:{edge}\n'.encode())
                    except Exception as e:
                        print(f"[Mouse] Failed to send ENTER: {e}")
                        return False
                    print(f"[Mouse] Pointer entered client via {edge}")
                    return True
                return True
            def on_click(x, y, button, pressed):
                if not pointer_on_server:
                    return
                pass
            def on_scroll(x, y, dx, dy):
                if not pointer_on_server:
                    return
                pass
            while mouse_sharing_running:
                pointer_on_server = True
                pointer_on_client = False
                show_cursor()
                with MouseListener(on_move=on_move, on_click=on_click, on_scroll=on_scroll) as listener:
                    while mouse_sharing_running:
                        if pointer_on_server:
                            time.sleep(0.01)
                        else:
                            try:
                                data = conn.recv(1024)
                                if not data:
                                    print("[Mouse] Client disconnected.")
                                    break
                                if b'RETURN' in data:
                                    pointer_on_server = True
                                    pointer_on_client = False
                                    show_cursor()
                                    if edge == 'Left':
                                        mouse.position = (0, height // 2)
                                    elif edge == 'Right':
                                        mouse.position = (width - 1, height // 2)
                                    elif edge == 'Top':
                                        mouse.position = (width // 2, 0)
                                    elif edge == 'Bottom':
                                        mouse.position = (width // 2, height - 1)
                                    print("[Mouse] Pointer returned to server")
                                    break
                            except Exception as e:
                                print(f"[Mouse] Server socket error: {e}")
                                break
                    if not mouse_sharing_running:
                        break
            conn.close()
        except Exception as e:
            print(f"[Mouse] Server main error: {e}")
        finally:
            s.close()
    mouse_sharing_thread = threading.Thread(target=server_thread, daemon=True)
    mouse_sharing_thread.start()

def start_mouse_share_client(ip, _):
    global mouse_sharing_thread, mouse_sharing_running
    mouse_sharing_running = True
    def client_thread():
        mouse = MouseController()
        width, height = get_screen_size()
        try:
            s = socket.socket()
            s.connect((ip, MOUSE_PORT))
            pointer_on_client = False
            ignore_edge_once = False
            entry_edge = None
            while mouse_sharing_running:
                try:
                    data = s.recv(1024)
                    if not data:
                        print("[Mouse] Server disconnected.")
                        break
                    lines = data.decode(errors='ignore').splitlines()
                    for line in lines:
                        if line.startswith('ENTER:'):
                            pointer_on_client = True
                            ignore_edge_once = True
                            entry_edge = line.split(':', 1)[1]
                            if entry_edge in ENTRY_EDGE_TO_CLIENT_POS:
                                mouse.position = ENTRY_EDGE_TO_CLIENT_POS[entry_edge](width, height)
                            print(f"[Mouse] Pointer entered client via {entry_edge}")
                        elif line == 'RETURN':
                            pointer_on_client = False
                            print("[Mouse] Pointer returned to server")
                        elif pointer_on_client:
                            try:
                                event = json.loads(line)
                                if event["type"] == "move":
                                    mouse.position = (event["x"], event["y"])
                                elif event["type"] == "click":
                                    btn_name = event["button"].split('.')[-1]
                                    btn = getattr(Button, btn_name, Button.left)
                                    if event["pressed"]:
                                        mouse.press(btn)
                                    else:
                                        mouse.release(btn)
                                elif event["type"] == "scroll":
                                    mouse.scroll(event["dx"], event["dy"])
                            except Exception as e:
                                print(f"[Mouse] Client event error: {e}")
                    if pointer_on_client and entry_edge:
                        x, y = mouse.position
                        if ignore_edge_once:
                            ignore_edge_once = False
                            continue
                        hit_edge = False
                        opp_edge = OPPOSITE_EDGE.get(entry_edge)
                        if opp_edge == 'Left' and x <= 0:
                            hit_edge = True
                        elif opp_edge == 'Right' and x >= width - 1:
                            hit_edge = True
                        elif opp_edge == 'Top' and y <= 0:
                            hit_edge = True
                        elif opp_edge == 'Bottom' and y >= height - 1:
                            hit_edge = True
                        if hit_edge:
                            pointer_on_client = False
                            try:
                                s.sendall(b'RETURN\n')
                            except Exception as e:
                                print(f"[Mouse] Client failed to send RETURN: {e}")
                            print("[Mouse] Pointer sent back to server")
                except Exception as e:
                    print(f"[Mouse] Client socket error: {e}")
                    break
            s.close()
        except Exception as e:
            print(f"[Mouse] Client main error: {e}")
    mouse_sharing_thread = threading.Thread(target=client_thread, daemon=True)
    mouse_sharing_thread.start()

class BarrierMinimal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Minimal Barrier")
        self.setFixedSize(400, 400)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        layout = QVBoxLayout()

        # Server group
        self.server_group = QGroupBox("Server (share this computer's mouse and keyboard):")
        self.server_group.setCheckable(True)
        self.server_group.setChecked(True)
        server_layout = QVBoxLayout()
        self.server_ip_label = QLabel("IP addresses: (auto-detect)")
        server_layout.addWidget(self.server_ip_label)
        # Client location config
        self.server_location_label = QLabel("Client location relative to server:")
        self.server_location_combo = QComboBox()
        self.server_location_combo.addItems(["Left", "Right", "Top", "Bottom"])
        server_layout.addWidget(self.server_location_label)
        server_layout.addWidget(self.server_location_combo)
        self.audio_checkbox = QCheckBox("Audio Share")
        server_layout.addWidget(self.audio_checkbox)
        self.server_group.setLayout(server_layout)
        layout.addWidget(self.server_group)

        # Client group
        self.client_group = QGroupBox("Client (use another computer's mouse and keyboard):")
        self.client_group.setCheckable(True)
        self.client_group.setChecked(False)
        client_layout = QVBoxLayout()
        self.client_ip_label = QLabel("Server IP:")
        self.client_ip_input = QLineEdit()
        client_layout.addWidget(self.client_ip_label)
        client_layout.addWidget(self.client_ip_input)
        # Remove client location config from GUI
        # self.client_location_label = QLabel("Location relative to server:")
        # self.client_location_combo = QComboBox()
        # self.client_location_combo.addItems(["Left", "Right", "Top", "Bottom"])
        # client_layout.addWidget(self.client_location_label)
        # client_layout.addWidget(self.client_location_combo)
        self.client_group.setLayout(client_layout)
        layout.addWidget(self.client_group)

        # Start/Stop buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        # Status label
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        central.setLayout(layout)
        self.setCentralWidget(central)

        # Connect signals
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.server_group.toggled.connect(self.on_server_toggled)
        self.client_group.toggled.connect(self.on_client_toggled)

    def toggle_audio_share(self, checked):
        # No GUI logic needed, handled in start/stop
        pass

    def start(self):
        self.status_label.setText("Started (minimal features)")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        # Start mouse sharing
        if self.server_group.isChecked():
            edge = self.server_location_combo.currentText()
            start_mouse_share_server(edge)
            if self.audio_checkbox.isChecked():
                start_audio_share('server')
        elif self.client_group.isChecked():
            ip = self.client_ip_input.text().strip()
            # edge is not needed on client, pass None
            if ip:
                start_mouse_share_client(ip, None)
                if self.audio_checkbox.isChecked():
                    start_audio_share('client', ip)

    def stop(self):
        self.status_label.setText("Stopped")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        stop_all_sharing()
        stop_audio_share()
        if self.audio_checkbox.isChecked():
            self.audio_checkbox.setChecked(False)

    def on_server_toggled(self, checked):
        if checked:
            self.client_group.setChecked(False)
        else:
            if not self.client_group.isChecked():
                self.server_group.setChecked(True)

    def on_client_toggled(self, checked):
        if checked:
            self.server_group.setChecked(False)
        else:
            if not self.server_group.isChecked():
                self.client_group.setChecked(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BarrierMinimal()
    window.show()
    sys.exit(app.exec_()) 