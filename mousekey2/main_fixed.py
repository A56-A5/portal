import json
import threading
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, 
                             QComboBox, QLineEdit, QPushButton, QLabel, 
                             QGroupBox, QRadioButton, QHBoxLayout, QMessageBox)
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from pynput import mouse, keyboard
from pynput.mouse import Controller as MouseController
from pynput.keyboard import Controller as KeyboardController
import pyperclip
import platform
import ctypes
import socket
import sys

class Communicate(QObject):
    status_signal = pyqtSignal(str, str)

class InputSharingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cross-Platform Input Sharing")
        self.setGeometry(100, 100, 400, 300)
        
        # Network settings
        self.server_ip = ""
        self.server_port = 5555
        self.client_socket = None
        self.server_socket = None
        self.running = False
        self.role = "server"
        self.connection_active = False
        self.last_message_time = 0
        
        # Screen edge configuration
        self.client_side = "right"
        
        # Input controllers
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        self.remote_control_active = False
        
        # Communication handler
        self.comm = Communicate()
        self.comm.status_signal.connect(self.show_status)
        
        # Initialize UI
        self.init_ui()
        
        # Clipboard monitoring
        self.last_clipboard_content = ""
        self.clipboard_monitor_thread = None
        self.clipboard_monitor_active = False
        
        # Platform-specific screen size detection
        self.screen_width, self.screen_height = self.get_screen_size()
        
        
    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        # Role selection
        role_group = QGroupBox("Device Role")
        role_layout = QHBoxLayout()
        self.server_radio = QRadioButton("Server")
        self.client_radio = QRadioButton("Client")
        self.server_radio.setChecked(True)
        role_layout.addWidget(self.server_radio)
        role_layout.addWidget(self.client_radio)
        role_group.setLayout(role_layout)
        
        # Server IP input
        self.ip_label = QLabel("Server IP:")
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("Enter server IP address")
        
        # Client side configuration
        side_group = QGroupBox("Client Screen Position (Server Only)")
        side_layout = QHBoxLayout()
        self.left_radio = QRadioButton("Left")
        self.right_radio = QRadioButton("Right")
        self.top_radio = QRadioButton("Top")
        self.bottom_radio = QRadioButton("Bottom")
        self.right_radio.setChecked(True)
        side_layout.addWidget(self.left_radio)
        side_layout.addWidget(self.right_radio)
        side_layout.addWidget(self.top_radio)
        side_layout.addWidget(self.bottom_radio)
        side_group.setLayout(side_layout)
        
        # Control buttons
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        
        # Add widgets to main layout
        layout.addWidget(role_group)
        layout.addWidget(self.ip_label)
        layout.addWidget(self.ip_input)
        layout.addWidget(side_group)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        
        # Connect signals
        self.server_radio.toggled.connect(self.update_role)
        self.start_btn.clicked.connect(self.start_sharing)
        self.stop_btn.clicked.connect(self.stop_sharing)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
    def update_role(self, checked):
        if checked:
            self.role = "server"
            self.ip_label.setText("Server IP:")
            self.ip_input.setPlaceholderText("Enter server IP address")
        else:
            self.role = "client"
            self.ip_label.setText("Server IP to connect:")
            self.ip_input.setPlaceholderText("Enter server IP address to connect")
    
    def start_sharing(self):
        self.server_ip = self.ip_input.text().strip()
        
        if self.role == "client" and not self.server_ip:
            self.show_status("Error", "Please enter server IP address")
            return
            
        # Update client side configuration
        if self.left_radio.isChecked():
            self.client_side = "left"
        elif self.right_radio.isChecked():
            self.client_side = "right"
        elif self.top_radio.isChecked():
            self.client_side = "top"
        elif self.bottom_radio.isChecked():
            self.client_side = "bottom"
        
        self.running = True
        
        if self.role == "server":
            threading.Thread(target=self.start_server, daemon=True).start()
        else:
            threading.Thread(target=self.connect_to_server, daemon=True).start()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # Start clipboard monitoring
        self.last_clipboard_content = pyperclip.paste()
        if not self.clipboard_monitor_active:
            self.clipboard_monitor_thread = threading.Thread(target=self.monitor_clipboard, daemon=True)
            self.clipboard_monitor_thread.start()
            self.clipboard_monitor_active = True
        
        self.show_status("Status", "Input sharing started as " + self.role)
    
    def stop_sharing(self):
        self.running = False
        self.connection_active = False
        
        if self.client_socket:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
                self.client_socket.close()
            except:
                pass
            finally:
                self.client_socket = None
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            finally:
                self.server_socket = None
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.show_status("Status", "Input sharing stopped")
    
    def show_status(self, title, message):
        print(f"[{title}] {message}")
        if title == "Error":
            QMessageBox.critical(self, title, message)
    
    def start_server(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind(('0.0.0.0', self.server_port))
            self.server_socket.listen(1)
            self.show_status("Server", f"Listening on port {self.server_port}...")
            
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    conn.settimeout(0.1)  # Short timeout for more responsive checks
                    self.connection_active = True
                    self.client_socket = conn
                    self.show_status("Server", f"Connected to {addr}")
                    
                    # Start a heartbeat thread
                    threading.Thread(target=self.send_heartbeat, daemon=True).start()
                    
                    # Start input handlers
                    mouse_listener = mouse.Listener(
                        on_move=self.on_server_mouse_move,
                        on_click=self.on_server_mouse_click,
                        on_scroll=self.on_server_mouse_scroll)
                    mouse_listener.start()
                    
                    keyboard_listener = keyboard.Listener(
                        on_press=self.on_server_key_press,
                        on_release=self.on_server_key_release)
                    keyboard_listener.start()
                    
                    # Handle connection
                    self.handle_connection(conn, mouse_listener, keyboard_listener)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.comm.status_signal.emit("Server Error", f"Connection error: {str(e)}")
                    continue
                
        except Exception as e:
            if self.running:
                self.comm.status_signal.emit("Server Error", str(e))
        finally:
            if self.server_socket:
                self.server_socket.close()
            self.connection_active = False
    
    def send_heartbeat(self):
        while self.running and self.connection_active:
            try:
                self.send_message("heartbeat")
                time.sleep(1)
            except:
                break
    
    def handle_connection(self, conn, mouse_listener, keyboard_listener):
        try:
            while self.running and self.connection_active:
                try:
                    data = conn.recv(4096)
                    if not data:
                        break
                        
                    try:
                        messages = data.decode().split('\n')
                        for msg in messages:
                            if msg.strip():
                                message = json.loads(msg)
                                if message["type"] == "heartbeat":
                                    continue
                                if self.role == "server":
                                    self.handle_client_message(message)
                                else:
                                    self.handle_server_message(message)
                    except json.JSONDecodeError:
                        continue
                    
                except socket.timeout:
                    continue
                except ConnectionResetError:
                    break
                except Exception as e:
                    self.comm.status_signal.emit("Error", f"Message handling error: {str(e)}")
                    break
                    
        finally:
            mouse_listener.stop()
            keyboard_listener.stop()
            try:
                conn.close()
            except:
                pass
            self.connection_active = False
            self.comm.status_signal.emit("Server", "Client disconnected")
    
    def connect_to_server(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.settimeout(5.0)
        
        try:
            self.client_socket.connect((self.server_ip, self.server_port))
            self.client_socket.settimeout(0.1)  # Short timeout for responsiveness
            self.connection_active = True
            self.show_status("Client", f"Connected to server at {self.server_ip}")
            
            # Start heartbeat
            threading.Thread(target=self.send_heartbeat, daemon=True).start()
            
            # Start input handlers
            mouse_listener = mouse.Listener(
                on_move=self.on_client_mouse_move,
                on_click=self.on_client_mouse_click,
                on_scroll=self.on_client_mouse_scroll)
            mouse_listener.start()
            
            keyboard_listener = keyboard.Listener(
                on_press=self.on_client_key_press,
                on_release=self.on_client_key_release)
            keyboard_listener.start()
            
            # Handle connection
            self.handle_connection(self.client_socket, mouse_listener, keyboard_listener)
            
        except socket.timeout:
            self.comm.status_signal.emit("Error", "Connection timed out")
        except Exception as e:
            if self.running:
                self.comm.status_signal.emit("Client Error", str(e))
        finally:
            self.connection_active = False
    
    def send_message(self, message_type, data=None):
        if not self.client_socket or not self.connection_active:
            return
            
        message = {"type": message_type}
        if data is not None:
            message["data"] = data
            
        try:
            self.client_socket.sendall((json.dumps(message) + '\n').encode())
            self.last_message_time = time.time()
        except:
            self.connection_active = False
    
    def get_screen_size(self):
        """Improved screen size detection that works cross-platform"""
        if platform.system() == "Windows":
            user32 = ctypes.windll.user32
            return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        elif platform.system() == "Linux":
            try:
                from Xlib import display
                d = display.Display()
                s = d.screen()
                return (s.width_in_pixels, s.height_in_pixels)
            except:
                return (1920, 1080)  # Fallback
        else:
            return (1920, 1080)  # Default fallback
    
    def on_server_mouse_move(self, x, y):
        if not self.connection_active:
            return
            
        # Update screen dimensions periodically
        if time.time() - self.last_message_time > 5:
            self.screen_width, self.screen_height = self.get_screen_size()
        
        # Check if mouse left the screen on the client side
        edge_threshold = 5  # pixels from edge to consider as edge
        if ((self.client_side == "left" and x <= edge_threshold) or
            (self.client_side == "right" and x >= self.screen_width - edge_threshold) or
            (self.client_side == "top" and y <= edge_threshold) or
            (self.client_side == "bottom" and y >= self.screen_height - edge_threshold)):
            
            # Only send if we're not already in remote control mode
            if not self.remote_control_active:
                self.remote_control_active = True
                
                # Normalize coordinates for client
                if self.client_side == "left":
                    client_x = self.screen_width - 1
                    client_y = y
                elif self.client_side == "right":
                    client_x = 0
                    client_y = y
                elif self.client_side == "top":
                    client_x = x
                    client_y = self.screen_height - 1
                else:  # bottom
                    client_x = x
                    client_y = 0
                    
                self.send_message("mouse_move", {
                    "x": client_x, 
                    "y": client_y,
                    "screen_width": self.screen_width,
                    "screen_height": self.screen_height
                })
    
    def on_client_mouse_move(self, x, y):
        if not self.connection_active:
            return
            
        # Update screen dimensions periodically
        if time.time() - self.last_message_time > 5:
            self.screen_width, self.screen_height = self.get_screen_size()
        
        # Check if mouse left the screen towards the server
        edge_threshold = 5  # pixels from edge to consider as edge
        if ((self.client_side == "left" and x <= edge_threshold) or
            (self.client_side == "right" and x >= self.screen_width - edge_threshold) or
            (self.client_side == "top" and y <= edge_threshold) or
            (self.client_side == "bottom" and y >= self.screen_height - edge_threshold)):
            
            if self.remote_control_active:
                self.remote_control_active = False
                self.send_message("mouse_move", {
                    "x": x,
                    "y": y,
                    "screen_width": self.screen_width,
                    "screen_height": self.screen_height
                })
    
    def on_client_mouse_click(self, x, y, button, pressed):
        self.send_message("mouse_click", {
            "x": x, "y": y, 
            "button": str(button), 
            "pressed": pressed
        })
    
    def on_client_mouse_scroll(self, x, y, dx, dy):
        self.send_message("mouse_scroll", {
            "x": x, "y": y,
            "dx": dx, "dy": dy
        })
    
    def on_client_key_press(self, key):
        try:
            self.send_message("key_press", {"key": str(key)})
        except:
            pass
    
    def on_client_key_release(self, key):
        try:
            self.send_message("key_release", {"key": str(key)})
        except:
            pass
    
    # Message handlers
    def handle_client_message(self, message):
        if message["type"] == "mouse_move":
            data = message["data"]
            if "screen_width" in data and "screen_height" in data:
                # Update our screen dimensions to match client
                self.screen_width = data["screen_width"]
                self.screen_height = data["screen_height"]
            
            self.remote_control_active = True
            self.mouse_controller.position = (data["x"], data["y"])
        
        elif message["type"] == "mouse_click":
            data = message["data"]
            button = mouse.Button[data["button"].split(".")[-1]]
            
            if data["pressed"]:
                self.mouse_controller.press(button)
            else:
                self.mouse_controller.release(button)
        
        elif message["type"] == "mouse_scroll":
            data = message["data"]
            self.mouse_controller.scroll(data["dx"], data["dy"])
        
        elif message["type"] == "key_press":
            data = message["data"]
            key = self.parse_key(data["key"])
            if key:
                self.keyboard_controller.press(key)
        
        elif message["type"] == "key_release":
            data = message["data"]
            key = self.parse_key(data["key"])
            if key:
                self.keyboard_controller.release(key)
        
        elif message["type"] == "clipboard_update":
            content = message["data"]["content"]
            if content != pyperclip.paste():
                pyperclip.copy(content)
    
    def handle_server_message(self, message):
        if message["type"] == "mouse_move":
            data = message["data"]
            if "screen_width" in data and "screen_height" in data:
                # Update our screen dimensions to match server
                self.screen_width = data["screen_width"]
                self.screen_height = data["screen_height"]
    
            self.remote_control_active = False
    
            # Adjust position based on client side
            if self.client_side == "left":
                new_x = self.screen_width - 1
                new_y = data["y"]
            elif self.client_side == "right":
                new_x = 0
                new_y = data["y"]
            elif self.client_side == "top":
                new_x = data["x"]
                new_y = self.screen_height - 1
            else:  # bottom
                new_x = data["x"]
                new_y = 0
    
            self.mouse_controller.position = (new_x, new_y)
    
        elif message["type"] == "mouse_click":
            data = message["data"]
            button = mouse.Button[data["button"].split(".")[-1]]
    
            if data["pressed"]:
                self.mouse_controller.press(button)
            else:
                self.mouse_controller.release(button)
    
        elif message["type"] == "mouse_scroll":
            data = message["data"]
            self.mouse_controller.scroll(data["dx"], data["dy"])
    
        elif message["type"] == "key_press":
            data = message["data"]
            key = self.parse_key(data["key"])
            if key:
                self.keyboard_controller.press(key)
    
        elif message["type"] == "key_release":
            data = message["data"]
            key = self.parse_key(data["key"])
            if key:
                self.keyboard_controller.release(key)
    
        elif message["type"] == "clipboard_update":
            content = message["data"]["content"]
            if content != pyperclip.paste():
                pyperclip.copy(content)


    
    def parse_key(self, key_str):
        try:
            # Try parsing special keys like 'Key.shift'
            if "Key." in key_str:
                return getattr(keyboard.Key, key_str.split(".")[-1])
            elif "'" in key_str:
                return key_str.strip("'")
            else:
                return key_str
        except AttributeError:
            return None

    
    def monitor_clipboard(self):
        while self.running:
            try:
                current = pyperclip.paste()
                if current != self.last_clipboard_content:
                    self.last_clipboard_content = current
                    self.send_message("clipboard_update", {"content": current})
                time.sleep(1)
            except Exception as e:
                print(f"[Clipboard Monitor] Error: {e}")
                time.sleep(1)

    
    def get_screen_size(self):
        # This is a simplified version - you might need platform-specific code
        # For a real implementation, consider using screeninfo package
        return (1920, 1080)  # Default to 1080p, adjust as needed
    
    def closeEvent(self, event):
        self.stop_sharing()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = InputSharingApp()
    window.show()
    sys.exit(app.exec_())