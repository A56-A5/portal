"""
Connection Handler - Manages network connections for mouse, keyboard, and clipboard sync
"""
import socket
import threading
import json
import time
import logging
import platform
from typing import Optional, Callable
from pynput.mouse import Button

from utils.config import app_config
from controllers.clipboard_controller import ClipboardController
from controllers.mouse_controller import MouseController
from controllers.keyboard_controller import KeyboardController
from network.input_handler import InputHandler


class ConnectionHandler:
    def __init__(self, on_state_change: Optional[Callable] = None):
        self.on_state_change = on_state_change
        
        self.primary_port = app_config.server_primary_port
        self.secondary_port = app_config.server_secondary_port
        
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.secondary_server_socket: Optional[socket.socket] = None
        self.secondary_client_socket: Optional[socket.socket] = None
        
        self.edge_transition_cooldown = False
        self.last_send = None
        
        # Controllers
        self.clipboard_controller = ClipboardController()
        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()
        
        # Input handler
        self.input_handler = InputHandler(self)
        
        # GUI and screen dimensions (will be set externally)
        self.gui_app = None
        self.screen_width = None
        self.screen_height = None
        self.overlay = None
        
        # Keyboard listener
        self.keyboard_listener = None
        self.keyboard_listener_lock = threading.Lock()
        
        self.os_type = platform.system().lower()
        
        logging.basicConfig(
            level=logging.INFO, 
            filename="logs.log", 
            filemode="a",
            format="%(levelname)s - %(message)s"
        )
        
        app_config.load()
        app_config.active_device = False
        app_config.save()
    
    def set_screen_info(self, gui_app, screen_width: int, screen_height: int):
        """Set GUI app and screen dimensions"""
        self.gui_app = gui_app
        self.screen_width = screen_width
        self.screen_height = screen_height
    
    def cleanup(self):
        """Clean up all sockets and resources"""
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
        """Create invisible overlay window"""
        if not app_config.active_device:
            return
        
        if self.os_type == "windows" and self.gui_app:
            import tkinter as tk
            overlay = tk.Toplevel(self.gui_app)
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
            from PyQt5.QtWidgets import QWidget
            from PyQt5.QtCore import Qt
            
            overlay = QWidget()
            overlay.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
            overlay.setAttribute(Qt.WA_TranslucentBackground)
            overlay.setCursor(Qt.BlankCursor)
            overlay.setGeometry(0, 0, self.screen_width, self.screen_height)
            overlay.setWindowOpacity(0.0)
            overlay.show()
            overlay.raise_()
            self.overlay = overlay
    
    def destroy_overlay(self):
        """Destroy overlay window"""
        if self.overlay:
            if self.os_type == "windows" and hasattr(self.overlay, 'destroy'):
                self.overlay.destroy()
            elif self.os_type == "linux" and hasattr(self.overlay, 'close'):
                self.overlay.close()
            self.overlay = None
    
    def monitor_mouse_edges(self, client_socket):
        """Monitor mouse edges for transitions"""
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
    
    def clipboard_sender(self, _socket, content: str):
        """Send clipboard content"""
        try:
            data = {"type": "clipboard", "content": content}
            _socket.sendall((json.dumps(data) + "\n").encode())
            print("[Clipboard] Sent clipboard data")
        except Exception as e:
            print(f"[Clipboard] Error: {e}")
    
    def transition(self, to_active, new_position):
        """Handle device transition"""
        app_config.load()
        app_config.active_device = to_active
        self.edge_transition_cooldown = True
        
        if self.os_type == "windows" and self.gui_app:
            self.gui_app.after_idle(self.create_overlay if to_active else self.destroy_overlay)
            self.mouse_controller.position = new_position
        else:
            if to_active:
                self.create_overlay()
            else:
                self.destroy_overlay()
            
            import win32api
            try:
                win32api.SetCursorPos(new_position)
            except (NameError, ImportError):
                self.mouse_controller.position = new_position
        
        if hasattr(self, 'secondary_server') and self.secondary_server:
            try:
                active_msg = {"type": "active_device", "value": to_active}
                self.secondary_server.sendall((json.dumps(active_msg) + "\n").encode())
            except Exception as e:
                print(f"[Transition] Failed to send active_device state: {e}")
                logging.info(f"[Transition] Failed to send active_device state: {e}")
        
        if to_active:
            current_clip = self.clipboard_controller.get_clipboard()
            if self.last_send != current_clip:
                self.last_send = current_clip
                if hasattr(self, 'secondary_server') and self.secondary_server:
                    self.clipboard_sender(self.secondary_server, current_clip)
        
        print(f"[System] Device {'Activated' if to_active else 'Deactivated'} at {new_position}")
        logging.info(f"[System] Device {'Activated' if to_active else 'Deactivated'} at {new_position}")
        app_config.save()
        time.sleep(0.2)
        
        if self.on_state_change:
            self.on_state_change(to_active)

