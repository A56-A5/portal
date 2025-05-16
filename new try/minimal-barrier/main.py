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
import pyautogui

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

pyautogui.FAILSAFE = False  # Disable failsafe for edge detection

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
    'Left': lambda w, h: (w - 2, h // 2),   # Enter from server's right, appear at right
    'Right': lambda w, h: (1, h // 2),      # Enter from server's left, appear at left
    'Top': lambda w, h: (w // 2, h - 2),    # Enter from server's bottom, appear at bottom
    'Bottom': lambda w, h: (w // 2, 1),     # Enter from server's top, appear at top
}

# Edge mapping for pointer return to server
RETURN_EDGE_TO_SERVER_POS = {
    'Left': lambda w, h: (0, h // 2),       # Return from client's right, appear at server's left
    'Right': lambda w, h: (w - 1, h // 2),  # Return from client's left, appear at server's right
    'Top': lambda w, h: (w // 2, 0),        # Return from client's bottom, appear at server's top
    'Bottom': lambda w, h: (w // 2, h - 1), # Return from client's top, appear at server's bottom
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

def stop_all_sharing():
    global mouse_sharing_running, mouse_sharing_thread
    mouse_sharing_running = False
    if mouse_sharing_thread and mouse_sharing_thread.is_alive():
        mouse_sharing_thread.join(timeout=1.0)
    pyautogui.moveTo(0, 0)  # Reset mouse position

def start_mouse_share_server(edge):
    global mouse_sharing_thread, mouse_sharing_running
    mouse_sharing_running = True
    def server_thread():
        global mouse_sharing_running
        width, height = pyautogui.size()
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', MOUSE_PORT))
        s.listen(1)
        print("[Mouse] Waiting for client connection...")
        conn, addr = s.accept()
        print(f"[Mouse] Client connected: {addr}")
        pointer_on_server = True
        edge_threshold = 5  # Pixels from edge to trigger transition

        while mouse_sharing_running:
            try:
                if pointer_on_server:
                    x, y = pyautogui.position()
                    # Check if mouse hits the selected edge
                    hit_edge = False
                    if edge == 'Left' and x <= edge_threshold:
                        hit_edge = True
                    elif edge == 'Right' and x >= width - edge_threshold:
                        hit_edge = True
                    elif edge == 'Top' and y <= edge_threshold:
                        hit_edge = True
                    elif edge == 'Bottom' and y >= height - edge_threshold:
                        hit_edge = True

                    if hit_edge:
                        pointer_on_server = False
                        # Send enter event to client with edge info
                        conn.sendall(f'ENTER:{edge}\n'.encode())
                        print(f"[Mouse] Pointer entered client via {edge}")
                        # Keep mouse at edge
                        if edge == 'Left':
                            pyautogui.moveTo(0, height // 2)
                        elif edge == 'Right':
                            pyautogui.moveTo(width - 1, height // 2)
                        elif edge == 'Top':
                            pyautogui.moveTo(width // 2, 0)
                        elif edge == 'Bottom':
                            pyautogui.moveTo(width // 2, height - 1)
                else:
                    # Listen for RETURN
                    data = conn.recv(1024)
                    if not data:
                        break
                    if b'RETURN' in data:
                        pointer_on_server = True
                        print("[Mouse] Pointer returned to server")
                        # Move pointer to correct edge on return
                        if edge == 'Left':
                            pyautogui.moveTo(edge_threshold, height // 2)
                        elif edge == 'Right':
                            pyautogui.moveTo(width - edge_threshold, height // 2)
                        elif edge == 'Top':
                            pyautogui.moveTo(width // 2, edge_threshold)
                        elif edge == 'Bottom':
                            pyautogui.moveTo(width // 2, height - edge_threshold)
                time.sleep(0.01)  # Small delay to prevent CPU overuse
            except Exception as e:
                print(f"[Mouse] Server error: {e}")
                break

        try:
            conn.close()
            s.close()
        except Exception:
            pass
        mouse_sharing_running = False

    mouse_sharing_thread = threading.Thread(target=server_thread, daemon=True)
    mouse_sharing_thread.start()

def start_mouse_share_client(ip, _):
    global mouse_sharing_thread, mouse_sharing_running
    mouse_sharing_running = True
    def client_thread():
        global mouse_sharing_running
        width, height = pyautogui.size()
        s = socket.socket()
        try:
            s.connect((ip, MOUSE_PORT))
        except Exception as e:
            print(f"[Mouse] Failed to connect to server: {e}")
            mouse_sharing_running = False
            return

        pointer_on_client = False
        ignore_edge_once = False
        entry_edge = None
        edge_threshold = 5  # Pixels from edge to trigger transition

        while mouse_sharing_running:
            try:
                data = s.recv(1024)
                if not data:
                    break
                lines = data.decode(errors='ignore').splitlines()
                for line in lines:
                    if line.startswith('ENTER:'):
                        pointer_on_client = True
                        ignore_edge_once = True
                        entry_edge = line.split(':', 1)[1]
                        # Place pointer at the correct entry edge on client
                        if entry_edge in ENTRY_EDGE_TO_CLIENT_POS:
                            pos = ENTRY_EDGE_TO_CLIENT_POS[entry_edge](width, height)
                            pyautogui.moveTo(pos[0], pos[1])
                            # Force the mouse to stay at the edge initially
                            time.sleep(0.1)
                            pyautogui.moveTo(pos[0], pos[1])
                        print(f"[Mouse] Pointer entered client via {entry_edge}")

                # Listen for mouse leaving client edge
                if pointer_on_client and entry_edge:
                    x, y = pyautogui.position()
                    if ignore_edge_once:
                        ignore_edge_once = False
                        continue
                    hit_edge = False
                    opp_edge = OPPOSITE_EDGE.get(entry_edge)
                    if opp_edge == 'Left' and x <= edge_threshold:
                        hit_edge = True
                    elif opp_edge == 'Right' and x >= width - edge_threshold:
                        hit_edge = True
                    elif opp_edge == 'Top' and y <= edge_threshold:
                        hit_edge = True
                    elif opp_edge == 'Bottom' and y >= height - edge_threshold:
                        hit_edge = True
                    if hit_edge:
                        s.sendall(b'RETURN\n')
                        pointer_on_client = False
                        print(f"[Mouse] Pointer leaving client via {opp_edge}")

                time.sleep(0.01)  # Small delay to prevent CPU overuse
            except Exception as e:
                print(f"[Mouse] Client error: {e}")
                break

        try:
            s.close()
        except Exception:
            pass
        mouse_sharing_running = False

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